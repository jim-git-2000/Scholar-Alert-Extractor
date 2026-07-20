from pathlib import Path

from scholar_alerts.config import load_source_rules
from scholar_alerts.source_detector import detect_source

RULES = load_source_rules(Path("config/sources.yaml"))


def test_google_sender_must_match_exactly():
    assert (
        detect_source("scholaralerts-noreply@google.com", "anything", None, RULES).source
        == "google_scholar"
    )
    assert detect_source("fake@google.com", "Scholar Alert", None, RULES).source is None


def test_ieee_requires_subject_or_document_link():
    assert (
        detect_source("no-reply@ieee.org", "IEEE Xplore Author Alert", None, RULES).source
        == "ieee_author_alert"
    )
    by_link = detect_source(
        "no-reply@xplore.ieee.org",
        "Your notification",
        "https://ieeexplore.ieee.org/document/12345678",
        RULES,
    )
    assert by_link.source == "ieee_author_alert"
    unmatched = detect_source("no-reply@ieee.org", "Password notice", "hello", RULES)
    assert unmatched.source is None
    assert unmatched.reason == "sender_matched_but_content_unmatched"


def test_ieee_search_matches_subject_is_supported():
    result = detect_source(
        "no-reply@ieee.org",
        "New Matches Available for Your Search",
        None,
        RULES,
    )
    assert result.source == "ieee_author_alert"


def test_ieee_domain_wildcard_is_forbidden():
    result = detect_source("other-service@ieee.org", "IEEE Xplore Author Alert", None, RULES)
    assert result.source is None
    assert result.reason == "source_unmatched"
