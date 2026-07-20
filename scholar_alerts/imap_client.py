from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from typing import Any

from scholar_alerts.config import Settings
from scholar_alerts.mime_parser import decode_header_value, extract_sender
from scholar_alerts.models import MessageSummary


class ImapOperationError(RuntimeError):
    code = "imap_operation_failed"


class ImapLoginError(ImapOperationError):
    code = "imap_login_failed"


class FolderNotFoundError(ImapOperationError):
    code = "folder_not_found"


class MessageFetchError(ImapOperationError):
    code = "message_fetch_failed"


class MessageBecameSeenError(ImapOperationError):
    code = "message_became_seen_during_fetch"


class MarkSeenError(ImapOperationError):
    code = "mark_seen_failed"


def _has_seen(flags: Any) -> bool:
    return any(
        (flag.decode(errors="ignore") if isinstance(flag, bytes) else str(flag)).casefold()
        == r"\seen".casefold()
        for flag in (flags or ())
    )


def _first(data: dict[Any, Any], *names: bytes) -> Any:
    for name in names:
        if name in data:
            return data[name]
        decoded = name.decode("ascii", errors="ignore")
        if decoded in data:
            return data[decoded]
    return None


class ImapMailClient:
    def __init__(self, settings: Settings, client_factory: Callable[..., Any] | None = None):
        self.settings = settings
        self._client_factory = client_factory
        self.client: Any | None = None

    def _new_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory(
                self.settings.imap_host,
                port=self.settings.imap_port,
                ssl=True,
                timeout=self.settings.imap_timeout_seconds,
            )
        from imapclient import IMAPClient

        return IMAPClient(
            self.settings.imap_host,
            port=self.settings.imap_port,
            ssl=True,
            timeout=self.settings.imap_timeout_seconds,
        )

    def connect(self) -> ImapMailClient:
        try:
            self.client = self._new_client()
            self.client.login(self.settings.imap_username, self.settings.imap_password)
            return self
        except Exception as exc:
            self.client = None
            raise ImapLoginError(f"IMAP 登录失败: {type(exc).__name__}") from exc

    def close(self) -> None:
        if self.client is None:
            return
        try:
            self.client.logout()
        except Exception:
            pass
        finally:
            self.client = None

    def __enter__(self) -> ImapMailClient:
        return self.connect()

    def __exit__(self, *_args: object) -> None:
        self.close()

    def list_folders(self) -> list[str]:
        assert self.client is not None
        try:
            folders = self.client.list_folders()
            return [
                name.decode("utf-8", errors="replace") if isinstance(name, bytes) else str(name)
                for _flags, _delimiter, name in folders
            ]
        except Exception as exc:
            raise ImapOperationError(f"无法列出文件夹: {type(exc).__name__}") from exc

    def select_folder(self, *, readonly: bool) -> dict[Any, Any]:
        assert self.client is not None
        try:
            return self.client.select_folder(self.settings.target_folder, readonly=readonly)
        except Exception as exc:
            raise FolderNotFoundError(
                f"无法选择目标文件夹 {self.settings.target_folder!r}: {type(exc).__name__}"
            ) from exc

    def unread_summaries(self, *, limit: int | None = None) -> list[MessageSummary]:
        assert self.client is not None
        try:
            uids = list(self.client.search(["UNSEEN"]))
            if not uids:
                return []
            response = self.client.fetch(
                uids,
                [
                    b"BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)]",
                    b"FLAGS",
                    b"INTERNALDATE",
                ],
            )
            summaries = [self._summary(int(uid), data) for uid, data in response.items()]
            summaries.sort(key=lambda item: (item.received_at, item.uid))
            return summaries[:limit] if limit is not None else summaries
        except ImapOperationError:
            raise
        except Exception as exc:
            raise MessageFetchError(f"扫描未读邮件失败: {type(exc).__name__}") from exc

    @staticmethod
    def _summary(uid: int, data: dict[Any, Any]) -> MessageSummary:
        raw = _first(
            data,
            b"BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)]",
            b"BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)]",
        ) or b""
        message = BytesParser(policy=policy.default).parsebytes(raw)
        internal_date = _first(data, b"INTERNALDATE")
        received_at: datetime
        if isinstance(internal_date, datetime):
            received_at = internal_date
        else:
            try:
                received_at = parsedate_to_datetime(message.get("Date"))
            except (TypeError, ValueError, OverflowError):
                received_at = datetime.now()
        if received_at.tzinfo is not None:
            received_at = received_at.astimezone().replace(tzinfo=None)
        flags = tuple(_first(data, b"FLAGS") or ())
        return MessageSummary(
            uid=uid,
            sender=extract_sender(message.get("From")),
            subject=decode_header_value(message.get("Subject")),
            received_at=received_at,
            flags=flags,
        )

    def fetch_raw_peek(self, uid: int) -> bytes:
        assert self.client is not None
        try:
            before_response = self.client.fetch([uid], [b"FLAGS"])
            before_flags = _first(before_response.get(uid, {}), b"FLAGS") or ()
            if _has_seen(before_flags):
                raise MessageBecameSeenError(f"UID {uid} 在读取前已变为已读")
            fetched = self.client.fetch([uid], [b"BODY.PEEK[]", b"FLAGS"])
            data = fetched.get(uid, {})
            raw = _first(data, b"BODY[]", b"BODY.PEEK[]", b"RFC822")
            after_response = self.client.fetch([uid], [b"FLAGS"])
            after_flags = _first(after_response.get(uid, {}), b"FLAGS") or ()
            if not _has_seen(before_flags) and _has_seen(after_flags):
                raise MessageBecameSeenError(f"UID {uid} 无痕读取后意外出现 \\Seen")
            if not isinstance(raw, bytes):
                raise MessageFetchError(f"UID {uid} 未返回完整邮件正文")
            return raw
        except ImapOperationError:
            raise
        except Exception as exc:
            raise MessageFetchError(f"UID {uid} 读取失败: {type(exc).__name__}") from exc

    def mark_seen(self, uid: int) -> None:
        assert self.client is not None
        try:
            self.client.add_flags([uid], [br"\Seen"], silent=True)
            response = self.client.fetch([uid], [b"FLAGS"])
            flags = _first(response.get(uid, {}), b"FLAGS") or ()
            if not _has_seen(flags):
                raise MarkSeenError(f"UID {uid} 添加 \\Seen 后验证失败")
        except MarkSeenError:
            raise
        except Exception as exc:
            raise MarkSeenError(f"UID {uid} 标记已读失败: {type(exc).__name__}") from exc
