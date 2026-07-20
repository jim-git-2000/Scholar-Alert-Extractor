from __future__ import annotations

from dataclasses import dataclass

from scholar_alerts.config import SourceRule


@dataclass(frozen=True, slots=True)
class Detection:
    source: str | None
    reason: str | None = None


def detect_source(
    sender: str,
    subject: str,
    body: str | None,
    rules: dict[str, SourceRule],
) -> Detection:
    normalized_sender = sender.strip().lower()
    google = rules.get("google_scholar")
    if google and google.enabled and normalized_sender in google.from_exact:
        return Detection("google_scholar")

    ieee = rules.get("ieee_author_alert")
    if ieee and ieee.enabled and normalized_sender in ieee.from_exact:
        lowered_subject = subject.casefold()
        lowered_body = (body or "").casefold()
        subject_matched = any(p.casefold() in lowered_subject for p in ieee.subject_patterns)
        link_matched = any(p.casefold() in lowered_body for p in ieee.required_link_patterns)
        if subject_matched or link_matched:
            return Detection("ieee_author_alert")
        return Detection(None, "sender_matched_but_content_unmatched")
    return Detection(None, "source_unmatched")

