from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Paper:
    title: str
    authors: list[str]
    year: int | None
    publication: str | None
    doi: str | None
    ieee_document_id: str | None
    paper_url: str | None
    pdf_url: str | None
    snippet: str | None
    source: str
    alert_name: str | None
    received_at: datetime
    message_id: str | None
    email_uid: int


@dataclass(slots=True)
class ParseResult:
    papers: list[Paper]
    source: str
    parser_name: str
    detected_items: int
    parsed_items: int
    failed_items: int
    warnings: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return (
            self.detected_items > 0
            and self.parsed_items > 0
            and self.failed_items == 0
            and self.parsed_items == self.detected_items
        )


@dataclass(slots=True)
class MimeMessage:
    sender: str
    subject: str
    received_at: datetime
    message_id: str | None
    html: str | None
    text: str | None


@dataclass(slots=True)
class MessageSummary:
    uid: int
    sender: str
    subject: str
    received_at: datetime
    flags: tuple[bytes, ...] = ()


@dataclass(slots=True)
class MergeResult:
    added: int
    duplicates: int
    total: int
    changed_keys: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProcessedMessage:
    uid: int
    source: str | None
    detected: int = 0
    added: int = 0
    duplicates: int = 0
    failed: int = 0
    marked_seen: bool = False
    error: str | None = None

