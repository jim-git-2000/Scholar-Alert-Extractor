from __future__ import annotations

import re
from collections import defaultdict

from bs4 import Tag

from scholar_alerts.dedup import deduplicate_papers
from scholar_alerts.models import MimeMessage, Paper, ParseResult
from scholar_alerts.normalizers import normalize_doi, normalize_ieee_document_id, normalize_url
from scholar_alerts.parsers.base import (
    URL_RE,
    AlertParser,
    clean_text,
    extract_year,
    lines_from_block,
    nearest_content_block,
    soup_for,
    split_authors,
)

_MANAGEMENT_WORDS = {
    "unsubscribe",
    "privacy policy",
    "manage alerts",
    "sign in",
    "login",
    "terms of use",
    "view in browser",
    "abstract",
    "pdf",
    "full text",
}
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", flags=re.I)


def _alert_name(subject: str, text: str | None) -> str | None:
    patterns = (
        r"(?:new content from|author alert(?:\s+for)?)\s*[:：-]?\s*([^|\n]+)",
        r"articles?\s+by\s+([^|\n]+)",
        r"(?:search query|saved search|search alert)\s*[:：-]\s*([^|\n]+)",
    )
    for value in (subject, (text or "")[:1000]):
        for pattern in patterns:
            match = re.search(pattern, value, flags=re.I)
            if match:
                name = clean_text(match.group(1))
                if name:
                    return name[:200]
    return None


def _title_for(link: Tag, block: Tag) -> str:
    link_text = clean_text(link.get_text(" ", strip=True))
    if link_text.casefold() not in _MANAGEMENT_WORDS and len(link_text) >= 6:
        return link_text
    for heading in block.find_all(["h1", "h2", "h3", "h4", "strong", "b", "a"]):
        value = clean_text(heading.get_text(" ", strip=True))
        if len(value) >= 6 and value.casefold() not in _MANAGEMENT_WORDS:
            return value
    return ""


def _fields(
    lines: list[str], title: str
) -> tuple[list[str], int | None, str | None, str | None, str | None]:
    useful = [line for line in lines if line != title]
    authors_line = next(
        (line for line in useful if re.match(r"^(?:authors?|by)\s*:", line, flags=re.I)),
        None,
    )
    publication_line = next(
        (
            line
            for line in useful
            if re.match(r"^(?:published in|publication|journal|conference)\s*:", line, flags=re.I)
        ),
        None,
    )
    doi_match = _DOI_RE.search(" ".join(useful))
    year = extract_year(publication_line or " ".join(useful))
    publication = None
    if publication_line:
        publication = clean_text(publication_line.split(":", 1)[-1])
        if year:
            publication = clean_text(re.sub(rf"[,;]?\s*{year}\b.*$", "", publication)) or None
    if not authors_line:
        authors_line = next(
            (
                line
                for line in useful
                if line != publication_line
                and not _DOI_RE.search(line)
                and not line.lower().startswith("http")
                and len(line) < 300
                and not extract_year(line)
            ),
            None,
        )
    authors = split_authors(authors_line)
    snippet = next(
        (
            line
            for line in useful
            if line not in {authors_line, publication_line}
            and not _DOI_RE.search(line)
            and len(line) > 40
        ),
        None,
    )
    doi = normalize_doi(doi_match.group(0)) if doi_match else None
    return authors, year, publication, doi, snippet


class IeeeAuthorAlertParser(AlertParser):
    source = "ieee_author_alert"
    parser_name = "ieee_author_alert_v1"

    def parse(self, message: MimeMessage, uid: int) -> ParseResult:
        soup = soup_for(message)
        grouped: dict[str, list[Tag]] = defaultdict(list)
        if soup is not None:
            for link in soup.find_all("a", href=True):
                document_id = normalize_ieee_document_id(str(link["href"]))
                if document_id and "ieeexplore.ieee.org" in str(link["href"]).casefold():
                    grouped[document_id].append(link)
        papers: list[Paper] = []
        failures = 0
        if grouped:
            for document_id, links in grouped.items():
                blocks = [nearest_content_block(link) for link in links]
                block = max(blocks, key=lambda item: len(item.get_text(" ", strip=True)))
                title = next(
                    (_title_for(link, block) for link in links if _title_for(link, block)),
                    "",
                )
                lines = lines_from_block(block)
                authors, year, publication, doi, snippet = _fields(lines, title)
                pdf_url = None
                for link in block.find_all("a", href=True):
                    href = str(link["href"])
                    text = clean_text(link.get_text(" ", strip=True))
                    if "pdf" in text.casefold() or ".pdf" in href.casefold() or "/stamp/" in href:
                        pdf_url = normalize_url(href)
                        break
                if not title:
                    failures += 1
                    continue
                papers.append(
                    Paper(
                        title=title,
                        authors=authors,
                        year=year,
                        publication=publication,
                        doi=doi,
                        ieee_document_id=document_id,
                        paper_url=f"https://ieeexplore.ieee.org/document/{document_id}",
                        pdf_url=pdf_url,
                        snippet=snippet,
                        source=self.source,
                        alert_name=_alert_name(message.subject, message.text),
                        received_at=message.received_at,
                        message_id=message.message_id,
                        email_uid=uid,
                    )
                )
        else:
            papers, failures = self._parse_text(message, uid)
        unique = deduplicate_papers(papers)
        return ParseResult(
            papers=unique,
            source=self.source,
            parser_name=self.parser_name,
            detected_items=len(unique) + failures,
            parsed_items=len(unique),
            failed_items=failures,
            warnings=["plain_text_fallback_used"] if not grouped and unique else [],
        )

    def _parse_text(self, message: MimeMessage, uid: int) -> tuple[list[Paper], int]:
        text = message.text or ""
        matches = list(
            re.finditer(
                r"https?://(?:www\.)?ieeexplore\.ieee\.org/document/(\d+)[^\s<]*",
                text,
                re.I,
            )
        )
        papers: list[Paper] = []
        failures = 0
        seen: set[str] = set()
        for match in matches:
            document_id = match.group(1)
            if document_id in seen:
                continue
            seen.add(document_id)
            before = text[max(0, match.start() - 1200) : match.start()]
            after = text[match.end() : match.end() + 1200]
            before_lines = [clean_text(line) for line in before.splitlines() if clean_text(line)]
            title = before_lines[-1] if before_lines else ""
            if title.casefold() in _MANAGEMENT_WORDS and len(before_lines) > 1:
                title = before_lines[-2]
            context = [title] + [clean_text(line) for line in after.splitlines()[:10]]
            authors, year, publication, doi, snippet = _fields(context, title)
            if len(title) < 6:
                failures += 1
                continue
            pdf_url = next(
                (normalize_url(url) for url in URL_RE.findall(after) if "pdf" in url.casefold()),
                None,
            )
            papers.append(
                Paper(
                    title=title,
                    authors=authors,
                    year=year,
                    publication=publication,
                    doi=doi,
                    ieee_document_id=document_id,
                    paper_url=f"https://ieeexplore.ieee.org/document/{document_id}",
                    pdf_url=pdf_url,
                    snippet=snippet,
                    source=self.source,
                    alert_name=_alert_name(message.subject, message.text),
                    received_at=message.received_at,
                    message_id=message.message_id,
                    email_uid=uid,
                )
            )
        return deduplicate_papers(papers), failures
