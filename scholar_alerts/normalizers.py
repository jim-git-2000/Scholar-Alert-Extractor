from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = {
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "trk",
    "trackingid",
    "source",
}
_DASHES = re.compile(
    r"[\u002d\u058a\u05be\u1400\u1806\u2010-\u2015\u2e17\u2e1a"
    r"\u2e3a-\u2e3b\u2e40\u301c\u3030\u30a0\ufe31-\ufe32\ufe58\ufe63\uff0d]"
)
_TITLE_PUNCTUATION = re.compile(r"[^\w\s-]", re.UNICODE)


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", html.unescape(value)).lower()
    text = _DASHES.sub("-", text)
    text = _TITLE_PUNCTUATION.sub(" ", text)
    text = re.sub(r"[-\s]+", " ", text)
    return text.strip()


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = html.unescape(value).strip().lower()
    doi = re.sub(r"^doi\s*:\s*", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = unquote(doi).strip()
    doi = re.sub(r"[\s.,;:!?\]\)}>]+$", "", doi)
    return doi or None


def decode_google_redirect(value: str) -> str:
    try:
        parts = urlsplit(html.unescape(value))
    except ValueError:
        return value
    host = (parts.hostname or "").lower()
    if host.endswith("google.com") or host.endswith("googleusercontent.com"):
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        target = query.get("url") or query.get("q")
        if target and target.startswith(("http://", "https://")):
            return unquote(target)
    return value


def normalize_ieee_document_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if re.fullmatch(r"\d{4,}", raw):
        return raw
    match = re.search(r"/document/(\d{4,})(?:/|\b|$)", raw, flags=re.I)
    return match.group(1) if match else None


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    raw = decode_google_redirect(html.unescape(value).strip())
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw or None
    if not parts.scheme or not parts.netloc:
        return raw or None
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    document_id = None
    if host in {"ieeexplore.ieee.org", "www.ieeexplore.ieee.org"}:
        document_id = normalize_ieee_document_id(parts.path)
    if document_id:
        return f"https://ieeexplore.ieee.org/document/{document_id}"
    query_items = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMS
    ]
    path = re.sub(r"/{2,}", "/", parts.path)
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, urlencode(query_items, doseq=True), ""))


def normalize_author(value: str | None) -> str:
    if not value:
        return ""
    author = unicodedata.normalize("NFKC", html.unescape(value)).lower()
    author = re.sub(r"\b(?:dr|prof|professor)\.?\s+", "", author)
    author = re.sub(r"[^\w\s-]", " ", author, flags=re.UNICODE)
    return re.sub(r"\s+", " ", author).strip()


def extract_first_author(authors: list[str] | str | None) -> str:
    if not authors:
        return ""
    if isinstance(authors, list):
        return normalize_author(authors[0]) if authors else ""
    first = re.split(r"\s*(?:,|;|\band\b|&|、)\s*", authors, maxsplit=1, flags=re.I)[0]
    return normalize_author(first)
