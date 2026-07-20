from scholar_alerts.mime_parser import parse_message


def test_multipart_prefers_html_sanitizes_and_ignores_attachment():
    raw = b"""From: =?UTF-8?B?5o+Q6YaS?= <scholaralerts-noreply@google.com>
Subject: =?UTF-8?B?U2Nob2xhciBBbGVydDogRE9B?=
Date: Wed, 01 Jul 2026 08:30:00 +0800
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary=x

--x
Content-Type: multipart/alternative; boundary=y

--y
Content-Type: text/plain; charset=utf-8

Plain body
--y
Content-Type: text/html; charset=utf-8

<html><style>.x{}</style><script>bad()</script><p>Visible</p>
<p hidden>Secret</p><img width="1" height="1"></html>
--y--
--x
Content-Type: text/plain; name=secret.txt
Content-Disposition: attachment; filename=secret.txt

Attachment text
--x--
"""
    message = parse_message(raw)
    assert message.sender == "scholaralerts-noreply@google.com"
    assert message.subject == "Scholar Alert: DOA"
    assert "Visible" in (message.html or "")
    assert "bad()" not in (message.html or "")
    assert "Secret" not in (message.text or "")
    assert "Attachment" not in (message.text or "")


def test_gbk_body_with_wrong_or_missing_charset_falls_back():
    body = "中文论文提醒".encode("gb18030")
    raw = b"From: a@example.com\nSubject: test\nContent-Type: text/plain\n\n" + body
    assert "中文论文提醒" in (parse_message(raw).text or "")
