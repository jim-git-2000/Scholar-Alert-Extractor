from __future__ import annotations

from datetime import datetime

from scholar_alerts.excel_store import ExcelStoreError
from scholar_alerts.imap_client import MarkSeenError
from scholar_alerts.models import MessageSummary
from scholar_alerts.processor import MessageProcessor
from tests.helpers import make_html_email

GOOD_HTML = """
<div><h3><a href="https://example.org/paper">A Complete Direction Finding Paper</a></h3>
<p>Alice Zhang - Signal Journal, 2026</p>
<p>This is a sufficiently long description of the complete paper result.</p></div>
"""


class FakeMail:
    def __init__(self, raw, *, mark_fails=False):
        self.raw = raw
        self.mark_fails = mark_fails
        self.marked = []

    def unread_summaries(self, limit=None):
        return [
            MessageSummary(
                uid=5,
                sender="scholaralerts-noreply@google.com",
                subject="Google Scholar Alert: DOA",
                received_at=datetime(2026, 7, 1),
            )
        ][:limit]

    def fetch_raw_peek(self, uid):
        assert uid == 5
        return self.raw

    def mark_seen(self, uid):
        if self.mark_fails:
            raise MarkSeenError("server refused")
        self.marked.append(uid)


class FailingStore:
    def apply(self, papers):
        raise ExcelStoreError("disk failed")

    def preview(self, papers):
        raise AssertionError("not expected")


def _raw(html=GOOD_HTML):
    return make_html_email(
        "scholaralerts-noreply@google.com", "Google Scholar Alert: DOA", html
    )


def test_success_writes_excel_then_marks_seen(settings_factory):
    settings = settings_factory()
    mail = FakeMail(_raw())
    result = MessageProcessor(settings).process_mailbox(mail)
    assert result[0].error is None
    assert result[0].added == 1
    assert result[0].marked_seen
    assert mail.marked == [5]
    assert settings.output_file.exists()


def test_zero_papers_keeps_message_unread_and_does_not_write(settings_factory):
    settings = settings_factory()
    mail = FakeMail(_raw("<p>No paper links in this changed template.</p>"))
    result = MessageProcessor(settings).process_mailbox(mail)
    assert result[0].error == "zero_valid_papers"
    assert not mail.marked
    assert not settings.output_file.exists()


def test_partial_parse_keeps_message_unread(settings_factory):
    settings = settings_factory()
    html = GOOD_HTML + """
    <div><h3>Broken Paper Without A Link</h3>
    <p>Bob Li - Array Journal, 2025</p></div>
    """
    mail = FakeMail(_raw(html))
    result = MessageProcessor(settings).process_mailbox(mail)
    assert result[0].error == "partial_parse"
    assert result[0].detected == 2
    assert not mail.marked
    assert not settings.output_file.exists()


def test_excel_failure_keeps_message_unread(settings_factory):
    settings = settings_factory()
    mail = FakeMail(_raw())
    result = MessageProcessor(settings, store=FailingStore()).process_mailbox(mail)
    assert result[0].error == "excel_save_failed"
    assert not mail.marked


def test_dry_run_changes_neither_excel_nor_flags(settings_factory):
    settings = settings_factory()
    mail = FakeMail(_raw())
    result = MessageProcessor(settings).process_mailbox(mail, dry_run=True)
    assert result[0].added == 1
    assert result[0].error is None
    assert not mail.marked
    assert not settings.output_file.exists()
    assert not (settings.output_file.parent / ".last_run.json").exists()


def test_mark_seen_failure_retains_committed_excel(settings_factory):
    settings = settings_factory()
    mail = FakeMail(_raw(), mark_fails=True)
    first = MessageProcessor(settings).process_mailbox(mail)
    assert first[0].error == "mark_seen_failed"
    assert settings.output_file.exists()
    second = MessageProcessor(settings).process_mailbox(FakeMail(_raw()))
    assert second[0].added == 0
    assert second[0].duplicates == 1
