from scholar_alerts.normalizers import (
    decode_google_redirect,
    extract_first_author,
    normalize_doi,
    normalize_ieee_document_id,
    normalize_title,
    normalize_url,
)


def test_normalize_title_unicode_entities_and_punctuation():
    assert normalize_title("  A&nbsp;Robust—Method: Test!  ") == "a robust method test"


def test_normalize_doi_variants():
    assert normalize_doi(" DOI: https://doi.org/10.1109/TSP.2025.123. ") == "10.1109/tsp.2025.123"
    assert normalize_doi("http://dx.doi.org/10.1000/ABC)") == "10.1000/abc"


def test_normalize_url_removes_tracking_fragment_and_canonicalizes_ieee():
    assert (
        normalize_url("HTTPS://IEEEXPLORE.IEEE.ORG/document/12345678/?utm_source=x#top")
        == "https://ieeexplore.ieee.org/document/12345678"
    )
    assert (
        normalize_url("https://Example.COM/paper/?utm_medium=email&a=1#x")
        == "https://example.com/paper?a=1"
    )


def test_google_redirect_decode():
    wrapped = "https://www.google.com/url?q=https%3A%2F%2Fexample.org%2Fpaper%3Fa%3D1&sa=D"
    assert decode_google_redirect(wrapped) == "https://example.org/paper?a=1"


def test_ieee_document_id_is_not_taken_from_unrelated_query_number():
    assert (
        normalize_ieee_document_id("https://ieeexplore.ieee.org/document/99887766/")
        == "99887766"
    )
    assert normalize_ieee_document_id("99887766") == "99887766"
    assert (
        normalize_ieee_document_id(
            "https://ieeexplore.ieee.org/search?arnumber=99887766"
        )
        is None
    )


def test_extract_first_author():
    assert extract_first_author(["Dr. Alice Zhang", "Bob Li"]) == "alice zhang"
