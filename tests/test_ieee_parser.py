from scholar_alerts.mime_parser import parse_message
from scholar_alerts.parsers.ieee_author_alert import IeeeAuthorAlertParser
from tests.helpers import make_html_email


def test_ieee_multiple_documents_group_links_and_extract_fields():
    html = """
    <html><body>
      <div class="paper-new-template">
        <h2><a href="https://ieeexplore.ieee.org/document/11112222?utm_source=alert">
          Sparse Array Design
        </a></h2>
        <p>Authors: Alice Zhang; Bob Li</p>
        <p>Published in: IEEE Transactions on Antennas, 2025</p>
        <p>DOI: 10.1109/TAP.2025.111</p>
        <p>A long abstract-like snippet about sparse array design and estimation.</p>
        <a href="https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=11112222">PDF</a>
        <a href="https://ieeexplore.ieee.org/document/11112222/">Abstract</a>
      </div>
      <article>
        <a href="https://ieeexplore.ieee.org/document/33334444">
          <b>Wideband Source Localization</b>
        </a>
        <div>By: Carol Wu and David Sun</div>
        <div>Publication: IEEE Access, 2024</div>
        <div>DOI: 10.1109/ACCESS.2024.222</div>
      </article>
      <footer><a href="https://ieee.org/unsubscribe">Unsubscribe</a></footer>
    </body></html>
    """
    message = parse_message(
        make_html_email(
            "no-reply@xplore.ieee.org", "IEEE Xplore Author Alert for Alice Zhang", html
        )
    )
    result = IeeeAuthorAlertParser().parse(message, 21)
    assert result.complete
    assert result.detected_items == 2
    first = result.papers[0]
    assert first.title == "Sparse Array Design"
    assert first.authors == ["Alice Zhang", "Bob Li"]
    assert first.year == 2025
    assert first.publication == "IEEE Transactions on Antennas"
    assert first.doi == "10.1109/tap.2025.111"
    assert first.ieee_document_id == "11112222"
    assert first.paper_url == "https://ieeexplore.ieee.org/document/11112222"
    assert first.pdf_url is not None
    assert first.alert_name == "Alice Zhang"


def test_ieee_plain_text_fallback():
    raw = b"""From: no-reply@ieee.org
Subject: New Content from Alice Zhang
Date: Wed, 01 Jul 2026 08:30:00 +0800
Content-Type: text/plain; charset=utf-8

Tensor Direction Estimation
https://ieeexplore.ieee.org/document/77778888
Authors: Alice Zhang; Bob Li
Publication: IEEE Signal Processing Letters, 2026
DOI: 10.1109/LSP.2026.777
"""
    result = IeeeAuthorAlertParser().parse(parse_message(raw), 22)
    assert result.complete
    assert result.papers[0].ieee_document_id == "77778888"
    assert result.papers[0].title == "Tensor Direction Estimation"
