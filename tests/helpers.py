def make_html_email(
    sender: str, subject: str, html: str, message_id: str = "fixture"
) -> bytes:
    return (
        f"From: Alert <{sender}>\r\n"
        f"Subject: {subject}\r\n"
        "Date: Wed, 01 Jul 2026 08:30:00 +0800\r\n"
        f"Message-ID: <{message_id}@example.test>\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Content-Transfer-Encoding: 8bit\r\n\r\n"
        f"{html}"
    ).encode()
