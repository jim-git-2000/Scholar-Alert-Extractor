from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from scholar_alerts.config import Settings
from scholar_alerts.dedup import deduplicate_papers
from scholar_alerts.excel_store import ExcelStore, ExcelStoreError
from scholar_alerts.imap_client import ImapMailClient, ImapOperationError, MarkSeenError
from scholar_alerts.logging_config import masked_sender
from scholar_alerts.mime_parser import MimeParseError, parse_message
from scholar_alerts.models import ProcessedMessage
from scholar_alerts.parsers import GoogleScholarParser, IeeeAuthorAlertParser
from scholar_alerts.source_detector import detect_source


LOGGER = logging.getLogger(__name__)


class MessageProcessingError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class MessageProcessor:
    def __init__(self, settings: Settings, store: ExcelStore | None = None):
        self.settings = settings
        self.store = store or ExcelStore(settings.output_file)
        self.parsers = {
            "google_scholar": GoogleScholarParser(),
            "ieee_author_alert": IeeeAuthorAlertParser(),
        }

    def process_mailbox(
        self,
        mail: ImapMailClient,
        *,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> list[ProcessedMessage]:
        effective_limit = min(
            limit or self.settings.max_emails_per_run,
            self.settings.max_emails_per_run,
        )
        summaries = mail.unread_summaries(limit=effective_limit)
        results: list[ProcessedMessage] = []
        dry_run_papers = []
        dry_run_added = 0
        dry_run_duplicates = 0
        for summary in summaries:
            result = ProcessedMessage(uid=summary.uid, source=None)
            try:
                raw = mail.fetch_raw_peek(summary.uid)
                try:
                    message = parse_message(raw)
                except MimeParseError as exc:
                    raise MessageProcessingError("mime_parse_failed", str(exc)) from exc
                message.received_at = summary.received_at
                detection = detect_source(
                    message.sender,
                    message.subject,
                    "\n".join(part for part in (message.html, message.text) if part),
                    self.settings.source_rules,
                )
                if detection.source is None:
                    raise MessageProcessingError(
                        detection.reason or "source_unmatched",
                        f"不处理发件人 {masked_sender(message.sender)} 的这封邮件",
                    )
                result.source = detection.source
                parsed = self.parsers[detection.source].parse(message, summary.uid)
                result.detected = parsed.detected_items
                result.failed = parsed.failed_items
                if parsed.detected_items == 0 or parsed.parsed_items == 0:
                    raise MessageProcessingError(
                        "zero_valid_papers", "邮件中未提取到有效论文"
                    )
                if not parsed.complete:
                    raise MessageProcessingError(
                        "partial_parse",
                        (
                            f"检测到 {parsed.detected_items} 条，"
                            f"仅成功解析 {parsed.parsed_items} 条"
                        ),
                    )
                papers = deduplicate_papers(parsed.papers)
                if dry_run:
                    dry_run_papers.extend(papers)
                    merge = self.store.preview(dry_run_papers)
                    result.added = merge.added - dry_run_added
                    result.duplicates = merge.duplicates - dry_run_duplicates
                    dry_run_added = merge.added
                    dry_run_duplicates = merge.duplicates
                else:
                    merge = self.store.apply(papers)
                    result.added = merge.added
                    result.duplicates = merge.duplicates
                if not dry_run:
                    try:
                        mail.mark_seen(summary.uid)
                        result.marked_seen = True
                    except MarkSeenError as exc:
                        result.error = exc.code
                        LOGGER.error(
                            "code=%s uid=%s source=%s detail=%s",
                            exc.code,
                            summary.uid,
                            detection.source,
                            exc,
                        )
                LOGGER.info(
                    "uid=%s source=%s sender=%s detected=%s added=%s duplicates=%s dry_run=%s",
                    summary.uid,
                    detection.source,
                    masked_sender(message.sender),
                    result.detected,
                    result.added,
                    result.duplicates,
                    dry_run,
                )
            except MessageProcessingError as exc:
                result.error = exc.code
                LOGGER.error("code=%s uid=%s detail=%s", exc.code, summary.uid, exc)
            except ExcelStoreError as exc:
                result.error = exc.code
                LOGGER.error("code=%s uid=%s detail=%s", exc.code, summary.uid, exc)
            except ImapOperationError as exc:
                result.error = exc.code
                log = (
                    LOGGER.critical
                    if exc.code == "message_became_seen_during_fetch"
                    else LOGGER.error
                )
                log("code=%s uid=%s detail=%s", exc.code, summary.uid, exc)
            except Exception as exc:
                result.error = "unhandled_error"
                LOGGER.exception(
                    "code=unhandled_error uid=%s type=%s",
                    summary.uid,
                    type(exc).__name__,
                )
            results.append(result)
        if not dry_run:
            write_last_run(self.settings.output_file.parent / ".last_run.json", results)
        return results


def write_last_run(path: Path, results: list[ProcessedMessage]) -> None:
    payload = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "processed": len(results),
        "added": sum(item.added for item in results),
        "duplicates": sum(item.duplicates for item in results),
        "errors": [
            {"uid": item.uid, "code": item.error} for item in results if item.error is not None
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".last-run-", delete=False
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        LOGGER.warning("无法保存最近运行状态: %s", type(exc).__name__)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_last_run(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
