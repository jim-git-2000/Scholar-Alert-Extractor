from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import Tag

from scholar_alerts.dedup import deduplicate_papers
from scholar_alerts.models import MimeMessage, Paper, ParseResult
from scholar_alerts.normalizers import decode_google_redirect, normalize_url
from scholar_alerts.parsers.base import (
    AlertParser,
    URL_RE,
    clean_text,
    extract_year,
    lines_from_block,
    nearest_content_block,
    soup_for,
    split_authors,
)


_IGNORED_TEXT = {
    "cited by",
    "related articles",
    "all versions",
    "cached",
    "create alert",
    "cancel alert",
    "my profile",
    "settings",
    "help",
    "unsubscribe",
    "view all",
}
_IGNORED_URL_PARTS = ("/scholar?cites=", "/scholar?cluster=", "unsubscribe", "accounts.google")


def _is_ignored_link(link: Tag) -> bool:
    text = clean_text(link.get_text(" ", strip=True)).casefold()
    href = str(link.get("href", "")).casefold()
    if not text or text in _IGNORED_TEXT:
        return True
    if any(text.startswith(prefix) for prefix in ("cited by ", "all ", "related ")):
        return True
    if any(item in href for item in _IGNORED_URL_PARTS):
        return True
    return href.startswith(("mailto:", "javascript:", "#"))


def _candidate_links(message: MimeMessage) -> list[Tag]:
    soup = soup_for(message)
    if soup is None:
        return []
    candidates: list[Tag] = []
    for link in soup.find_all("a", href=True):
        if _is_ignored_link(link):
            continue
        title = clean_text(link.get_text(" ", strip=True))
        href = str(link["href"])
        if len(title) < 6 or not href.startswith(("http://", "https://")):
            continue
        if re.search(r"\b(?:pdf|full text)\b", title, flags=re.I) or href.lower().endswith(".pdf"):
            continue
        semantic_parent = link.find_parent(["h2", "h3", "h4", "strong", "b"])
        block = nearest_content_block(link)
        block_text = block.get_text(" ", strip=True)
        has_metadata = bool(extract_year(block_text) or re.search(r"\s[-–—]\s", block_text))
        if semantic_parent is not None or (len(title) >= 14 and has_metadata):
            candidates.append(link)
    return candidates


def _unparsed_heading_count(message: MimeMessage, candidates: list[Tag]) -> int:
    soup = soup_for(message)
    if soup is None:
        return 0
    candidate_headings = {
        id(heading)
        for link in candidates
        if (heading := link.find_parent(["h2", "h3", "h4"])) is not None
    }
    failed = 0
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if id(heading) in candidate_headings:
            continue
        title = clean_text(heading.get_text(" ", strip=True))
        siblings = heading.find_next_siblings(limit=2)
        context = " ".join(item.get_text(" ", strip=True) for item in siblings)
        if (
            len(title) >= 6
            and title.casefold() not in _IGNORED_TEXT
            and not re.search(r"(?:google\s+scholar|scholar\s+alert)", title, flags=re.I)
            and (extract_year(context) or re.search(r"\s[-–—]\s", context))
        ):
            failed += 1
    return failed


def _alert_name(subject: str) -> str | None:
    value = re.sub(
        r"^(?:google scholar|scholar)\s+(?:alert|alerts|快讯)\s*[:：-]?\s*",
        "",
        subject,
        flags=re.I,
    ).strip()
    return value or None


def _metadata(lines: list[str], title: str) -> tuple[list[str], int | None, str | None, str | None]:
    useful = [line for line in lines if line != title and line.casefold() not in _IGNORED_TEXT]
    meta = next(
        (line for line in useful if extract_year(line) or re.search(r"\s[-–—]\s", line)),
        None,
    )
    if not meta:
        snippet = next((line for line in useful if len(line) > 30), None)
        return [], None, None, snippet
    chunks = [clean_text(item) for item in re.split(r"\s+[-–—]\s+", meta) if clean_text(item)]
    authors = split_authors(chunks[0]) if chunks else []
    year = extract_year(meta)
    publication = chunks[1] if len(chunks) > 1 else None
    if publication and year:
        publication = clean_text(re.sub(rf"[,;]?\s*{year}\b.*$", "", publication)) or None
    snippet = next((line for line in useful if line != meta and len(line) > 30), None)
    return authors, year, publication, snippet


class GoogleScholarParser(AlertParser):
    source = "google_scholar"
    parser_name = "google_scholar_v1"

    def parse(self, message: MimeMessage, uid: int) -> ParseResult:
        links = _candidate_links(message)
        papers: list[Paper] = []
        failures = 0
        warnings: list[str] = []
        if links:
            failures += _unparsed_heading_count(message, links)
            for link in links:
                title = clean_text(link.get_text(" ", strip=True))
                href = urljoin("https://scholar.google.com", str(link.get("href", "")))
                paper_url = normalize_url(decode_google_redirect(href))
                block = nearest_content_block(link)
                lines = lines_from_block(block)
                authors, year, publication, snippet = _metadata(lines, title)
                pdf_url = None
                for other in block.find_all("a", href=True):
                    other_text = clean_text(other.get_text(" ", strip=True))
                    other_href = urljoin(href, str(other["href"]))
                    if re.search(r"\bpdf\b", other_text, flags=re.I) or re.search(
                        r"\.pdf(?:[?#]|$)", other_href, flags=re.I
                    ):
                        pdf_url = normalize_url(decode_google_redirect(other_href))
                        break
                if not title or not paper_url:
                    failures += 1
                    continue
                papers.append(
                    Paper(
                        title=title,
                        authors=authors,
                        year=year,
                        publication=publication,
                        doi=None,
                        ieee_document_id=None,
                        paper_url=paper_url,
                        pdf_url=pdf_url,
                        snippet=snippet,
                        source=self.source,
                        alert_name=_alert_name(message.subject),
                        received_at=message.received_at,
                        message_id=message.message_id,
                        email_uid=uid,
                    )
                )
        else:
            papers, failures = self._parse_text(message, uid)
            if papers:
                warnings.append("html_candidates_missing_plain_text_fallback_used")
        unique = deduplicate_papers(papers)
        detected = len(unique) + failures
        return ParseResult(
            papers=unique,
            source=self.source,
            parser_name=self.parser_name,
            detected_items=detected,
            parsed_items=len(unique),
            failed_items=failures,
            warnings=warnings,
        )

    def _parse_text(self, message: MimeMessage, uid: int) -> tuple[list[Paper], int]:
        lines = [clean_text(line) for line in (message.text or "").splitlines()]
        lines = [line for line in lines if line]
        papers: list[Paper] = []
        for index, line in enumerate(lines):
            urls = URL_RE.findall(line)
            for url in urls:
                clean_url = normalize_url(decode_google_redirect(url.rstrip(".,)>")))
                if not clean_url or any(
                    item in clean_url.casefold() for item in _IGNORED_URL_PARTS
                ):
                    continue
                if re.search(r"\.pdf(?:[?#]|$)", clean_url, flags=re.I):
                    continue
                prefix = clean_text(line.replace(url, ""))
                title = prefix or (lines[index - 1] if index else "")
                if len(title) < 6 or title.casefold() in _IGNORED_TEXT:
                    continue
                context = lines[index + 1 : index + 4]
                authors, year, publication, snippet = _metadata(context, title)
                papers.append(
                    Paper(
                        title=title,
                        authors=authors,
                        year=year,
                        publication=publication,
                        doi=None,
                        ieee_document_id=None,
                        paper_url=clean_url,
                        pdf_url=next(
                            (
                                normalize_url(found)
                                for ctx in context
                                for found in URL_RE.findall(ctx)
                                if ".pdf" in found.casefold()
                            ),
                            None,
                        ),
                        snippet=snippet,
                        source=self.source,
                        alert_name=_alert_name(message.subject),
                        received_at=message.received_at,
                        message_id=message.message_id,
                        email_uid=uid,
                    )
                )
        return deduplicate_papers(papers), 0
