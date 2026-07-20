from __future__ import annotations

import re
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup, Tag

from scholar_alerts.models import MimeMessage, ParseResult


YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
URL_RE = re.compile(r"https?://[^\s<>\]\[\"']+")


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" \t\r\n-|•")


def split_authors(value: str | None) -> list[str]:
    text = clean_text(value)
    text = re.sub(r"^(?:authors?|by)\s*:\s*", "", text, flags=re.I)
    if not text:
        return []
    if ";" in text:
        parts = text.split(";")
    elif re.search(r"\s+(?:and|&)\s+", text, flags=re.I):
        parts = re.split(r"\s+(?:and|&)\s+", text, flags=re.I)
    else:
        parts = text.split(",")
    return [clean_text(item) for item in parts if clean_text(item)]


def extract_year(value: str | None) -> int | None:
    matches = YEAR_RE.findall(value or "")
    return int(matches[-1]) if matches else None


def nearest_content_block(link: Tag, *, max_chars: int = 4000) -> Tag:
    best = link.parent if isinstance(link.parent, Tag) else link
    for parent in link.parents:
        if not isinstance(parent, Tag) or parent.name in {"body", "html"}:
            break
        text = parent.get_text(" ", strip=True)
        links = parent.find_all("a", href=True)
        if len(text) <= max_chars and (
            len(text) >= len(link.get_text(strip=True)) + 15 or len(links) > 1
        ):
            return parent
        if len(text) > max_chars or len(links) > 12:
            break
    return best


def lines_from_block(block: Tag) -> list[str]:
    raw = block.get_text("\n", strip=True)
    return [clean_text(line) for line in raw.splitlines() if clean_text(line)]


class AlertParser(ABC):
    source: str
    parser_name: str

    @abstractmethod
    def parse(self, message: MimeMessage, uid: int) -> ParseResult: ...


def soup_for(message: MimeMessage) -> BeautifulSoup | None:
    return BeautifulSoup(message.html, "html.parser") if message.html else None
