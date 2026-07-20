from __future__ import annotations

from dataclasses import replace

from scholar_alerts.models import Paper
from scholar_alerts.normalizers import (
    extract_first_author,
    normalize_doi,
    normalize_ieee_document_id,
    normalize_title,
    normalize_url,
)


def candidate_keys(paper: Paper) -> list[str]:
    keys: list[str] = []
    doi = normalize_doi(paper.doi)
    document_id = normalize_ieee_document_id(paper.ieee_document_id)
    url = normalize_url(paper.paper_url)
    title = normalize_title(paper.title)
    first_author = extract_first_author(paper.authors)
    if doi:
        keys.append(f"doi:{doi}")
    if document_id:
        keys.append(f"ieee:{document_id}")
    if url:
        keys.append(f"url:{url}")
    if title and paper.year is not None:
        keys.append(f"title-year:{title}:{paper.year}")
    if title and first_author:
        keys.append(f"title-author:{title}:{first_author}")
    return keys


def dedup_key(paper: Paper) -> str:
    keys = candidate_keys(paper)
    if not keys:
        raise ValueError("论文缺少可用于去重的字段")
    return keys[0]


def matching_key(left: Paper, right: Paper) -> str | None:
    """Return the strongest common key while guarding known false-positive cases."""
    left_doi = normalize_doi(left.doi)
    right_doi = normalize_doi(right.doi)
    if left_doi and right_doi:
        return f"doi:{left_doi}" if left_doi == right_doi else None
    left_document = normalize_ieee_document_id(left.ieee_document_id)
    right_document = normalize_ieee_document_id(right.ieee_document_id)
    if left_document and right_document:
        return f"ieee:{left_document}" if left_document == right_document else None
    right_keys = set(candidate_keys(right))
    for key in candidate_keys(left):
        if key not in right_keys:
            continue
        if (
            key.startswith("title-author:")
            and left.year is not None
            and right.year is not None
            and left.year != right.year
        ):
            continue
        return key
    return None


def _prefer(existing: Paper, incoming: Paper) -> Paper:
    values = {}
    for field_name in (
        "authors",
        "year",
        "publication",
        "doi",
        "ieee_document_id",
        "paper_url",
        "pdf_url",
        "snippet",
        "alert_name",
    ):
        old = getattr(existing, field_name)
        new = getattr(incoming, field_name)
        values[field_name] = old if old not in (None, "", []) else new
    sources = [
        source.strip()
        for value in (existing.source, incoming.source)
        for source in value.split(";")
        if source.strip()
    ]
    values["source"] = "; ".join(dict.fromkeys(sources))
    return replace(existing, **values)


def deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    unique: list[Paper] = []
    for paper in papers:
        match = next(
            (index for index, existing in enumerate(unique) if matching_key(paper, existing)),
            None,
        )
        if match is None:
            unique.append(paper)
        else:
            unique[match] = _prefer(unique[match], paper)
    return unique
