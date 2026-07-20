from __future__ import annotations

import re
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from bs4 import BeautifulSoup

from scholar_alerts.models import MimeMessage


class MimeParseError(ValueError):
    """The message cannot be decoded safely."""


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (LookupError, UnicodeError):
        return value.strip()


def extract_sender(value: str | None) -> str:
    decoded = decode_header_value(value)
    return parseaddr(decoded)[1].strip().lower()


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    declared = part.get_content_charset()
    charsets = [item for item in (declared, "utf-8", "gb18030", "latin-1") if item]
    for charset in dict.fromkeys(charsets):
        try:
            return payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def sanitize_html(raw_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "iframe", "form", "noscript", "template"]):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if tag.parent is None or tag.attrs is None:
            continue
        style = re.sub(r"\s+", "", str(tag.get("style", "")).lower())
        hidden = tag.has_attr("hidden") or str(tag.get("aria-hidden", "")).lower() == "true"
        if hidden or "display:none" in style or "visibility:hidden" in style:
            tag.decompose()
            continue
        if tag.name == "img":
            width = str(tag.get("width", "")).strip().lower().removesuffix("px")
            height = str(tag.get("height", "")).strip().lower().removesuffix("px")
            if width in {"0", "1"} or height in {"0", "1"}:
                tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return str(soup), text


def _received_at(message: Message) -> datetime:
    value = message.get("Date")
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except (TypeError, ValueError, OverflowError):
            pass
    return datetime.now().replace(microsecond=0)


def parse_message(raw: bytes) -> MimeMessage:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception as exc:
        raise MimeParseError(f"无法解析邮件结构: {exc}") from exc

    html_parts: list[str] = []
    text_parts: list[str] = []
    parts = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        if part.is_multipart():
            continue
        disposition = (part.get_content_disposition() or "").lower()
        if disposition == "attachment" or part.get_filename():
            continue
        content_type = part.get_content_type().lower()
        if content_type not in {"text/html", "text/plain"}:
            continue
        decoded = _decode_part(part)
        if content_type == "text/html":
            html_parts.append(decoded)
        else:
            text_parts.append(decoded)

    clean_html = None
    html_text = ""
    if html_parts:
        clean_html, html_text = sanitize_html("\n".join(html_parts))
    plain_text = "\n".join(part.strip() for part in text_parts if part.strip()) or None
    if not plain_text and html_text:
        plain_text = html_text
    if clean_html is None and plain_text is None:
        raise MimeParseError("邮件不包含可处理的 HTML 或纯文本正文")
    return MimeMessage(
        sender=extract_sender(message.get("From")),
        subject=decode_header_value(message.get("Subject")),
        received_at=_received_at(message),
        message_id=(message.get("Message-ID") or "").strip() or None,
        html=clean_html,
        text=plain_text,
    )
