from scholar_alerts.mime_parser import parse_message
from scholar_alerts.parsers.google_scholar import GoogleScholarParser
from tests.helpers import make_html_email


def test_google_html_multiple_papers_and_ignored_action_links():
    html = """
    <html><body>
      <div class="random-a">
        <h3><a href="https://www.google.com/url?q=https%3A%2F%2Fexample.org%2Fone">
          First DOA Paper
        </a></h3>
        <div>Alice Zhang, Bob Li - Signal Processing, 2025 - example.org</div>
        <div>This is the first sufficiently detailed paper snippet for testing.</div>
        <a href="https://example.org/one.pdf">[PDF]</a>
        <a href="https://scholar.google.com/scholar?cites=1">Cited by 10</a>
      </div>
      <section data-layout="changed">
        <strong><a href="https://example.net/two">Second Array Processing Paper</a></strong>
        <p>Carol Wu and David Sun - IEEE Access, 2024 - example.net</p>
        <p>This is the second sufficiently detailed paper snippet for testing.</p>
        <a href="https://scholar.google.com/scholar?cluster=2">All versions</a>
      </section>
      <footer><a href="https://google.com/unsubscribe">Unsubscribe</a></footer>
    </body></html>
    """
    message = parse_message(
        make_html_email("scholaralerts-noreply@google.com", "Google Scholar Alert: DOA", html)
    )
    result = GoogleScholarParser().parse(message, 11)
    assert result.complete
    assert result.detected_items == 2
    assert [paper.title for paper in result.papers] == [
        "First DOA Paper",
        "Second Array Processing Paper",
    ]
    assert result.papers[0].authors == ["Alice Zhang", "Bob Li"]
    assert result.papers[0].year == 2025
    assert result.papers[0].publication == "Signal Processing"
    assert result.papers[0].paper_url == "https://example.org/one"
    assert result.papers[0].pdf_url == "https://example.org/one.pdf"
    assert result.papers[0].alert_name == "DOA"


def test_google_plain_text_fallback():
    raw = b"""From: scholaralerts-noreply@google.com
Subject: Scholar Alert: MUSIC
Date: Wed, 01 Jul 2026 08:30:00 +0800
Content-Type: text/plain; charset=utf-8

Plain Text Direction Finding
https://example.org/plain
Alice Zhang - Array Journal, 2023
This is a long result summary included in the plain text alert.
"""
    result = GoogleScholarParser().parse(parse_message(raw), 12)
    assert result.complete
    assert result.papers[0].title == "Plain Text Direction Finding"
    assert result.papers[0].year == 2023


def test_google_reports_partial_parse_for_broken_result_heading():
    html = """
    <div><h3><a href="https://example.org/good">Complete Paper</a></h3>
    <p>Alice Zhang - Signal Journal, 2026</p></div>
    <div><h3>Broken Paper Without A Link</h3>
    <p>Bob Li - Array Journal, 2025</p></div>
    """
    message = parse_message(
        make_html_email("scholaralerts-noreply@google.com", "Scholar Alert: DOA", html)
    )
    result = GoogleScholarParser().parse(message, 13)
    assert result.detected_items == 2
    assert result.parsed_items == 1
    assert result.failed_items == 1
    assert not result.complete
