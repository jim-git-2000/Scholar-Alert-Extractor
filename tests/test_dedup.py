from scholar_alerts.dedup import candidate_keys, dedup_key, deduplicate_papers


def test_dedup_priority(paper_factory):
    paper = paper_factory()
    assert dedup_key(paper) == "doi:10.1109/tsp.2025.12345"
    assert candidate_keys(paper)[1] == "ieee:12345678"


def test_cross_source_doi_duplicate_merges_without_losing_metadata(paper_factory):
    ieee = paper_factory()
    google = paper_factory(
        source="google_scholar",
        ieee_document_id=None,
        paper_url="https://example.org/preprint",
        publication=None,
    )
    result = deduplicate_papers([ieee, google])
    assert len(result) == 1
    assert result[0].publication == "IEEE Transactions on Signal Processing"
    assert set(result[0].source.split("; ")) == {"google_scholar", "ieee_author_alert"}


def test_same_title_different_year_is_not_merged_even_with_same_author(paper_factory):
    first = paper_factory(doi=None, ieee_document_id=None, paper_url=None, year=2024)
    second = paper_factory(doi=None, ieee_document_id=None, paper_url=None, year=2025)
    assert len(deduplicate_papers([first, second])) == 2


def test_title_and_first_author_can_merge_cross_source(paper_factory):
    first = paper_factory(doi=None, ieee_document_id=None, paper_url=None, year=None)
    second = paper_factory(
        doi=None,
        ieee_document_id=None,
        paper_url=None,
        year=None,
        source="google_scholar",
    )
    assert len(deduplicate_papers([first, second])) == 1


def test_conflicting_dois_do_not_fall_back_to_same_title_and_year(paper_factory):
    first = paper_factory(doi="10.1000/first", ieee_document_id=None, paper_url=None)
    second = paper_factory(doi="10.1000/second", ieee_document_id=None, paper_url=None)
    assert len(deduplicate_papers([first, second])) == 2
