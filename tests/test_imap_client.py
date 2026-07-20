from __future__ import annotations

from datetime import UTC, datetime

import pytest

from scholar_alerts.imap_client import ImapMailClient, MarkSeenError, MessageBecameSeenError

RAW = b"""From: Scholar <scholaralerts-noreply@google.com>
Subject: Scholar Alert: DOA
Date: Wed, 01 Jul 2026 08:30:00 +0800
Content-Type: text/plain; charset=utf-8

Paper
"""


class FakeImap:
    def __init__(self, *_args, become_seen=False, refuse_seen=False, **_kwargs):
        self.flags = {10: []}
        self.become_seen = become_seen
        self.refuse_seen = refuse_seen
        self.fetch_requests = []
        self.selected = None
        self.logged_out = False
        self.client_id = None

    def login(self, username, password):
        assert username == "user@example.test"
        assert password == "secret-token"

    def logout(self):
        self.logged_out = True

    def has_capability(self, capability):
        return capability == b"ID"

    def id_(self, parameters):
        self.client_id = parameters
        return {b"name": b"Coremail"}

    def list_folders(self):
        return [((), "/", "INBOX"), ((), "/", "论文提醒")]

    def select_folder(self, folder, readonly):
        self.selected = (folder, readonly)
        return {b"EXISTS": 1}

    def search(self, criteria):
        assert criteria == ["UNSEEN"]
        return [10]

    def fetch(self, uids, items):
        self.fetch_requests.append(items)
        uid = list(uids)[0]
        if any(b"HEADER.FIELDS" in item for item in items):
            headers = RAW.split(b"\n\n", 1)[0] + b"\n\n"
            return {
                uid: {
                    b"BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)]": headers,
                    b"FLAGS": tuple(self.flags[uid]),
                    b"INTERNALDATE": datetime(2026, 7, 1, tzinfo=UTC),
                }
            }
        if b"BODY.PEEK[]" in items:
            if self.become_seen:
                self.flags[uid].append(br"\Seen")
            return {uid: {b"BODY[]": RAW, b"FLAGS": tuple(self.flags[uid])}}
        return {uid: {b"FLAGS": tuple(self.flags[uid])}}

    def add_flags(self, uids, flags, silent):
        assert silent is True
        if not self.refuse_seen:
            self.flags[list(uids)[0]].extend(flags)


def _mail(settings_factory, fake):
    return ImapMailClient(settings_factory(), client_factory=lambda *_args, **_kwargs: fake)


def test_list_scan_and_body_peek_do_not_set_seen(settings_factory):
    fake = FakeImap()
    with _mail(settings_factory, fake) as mail:
        assert mail.list_folders() == ["INBOX", "论文提醒"]
        mail.select_folder(readonly=True)
        summaries = mail.unread_summaries()
        assert summaries[0].uid == 10
        assert summaries[0].sender == "scholaralerts-noreply@google.com"
        assert mail.fetch_raw_peek(10) == RAW
    assert any(b"BODY.PEEK[]" in request for request in fake.fetch_requests)
    assert not fake.flags[10]
    assert fake.client_id["name"] == "Scholar Alert Extractor"
    assert fake.logged_out


def test_unexpected_seen_after_peek_is_fatal(settings_factory):
    fake = FakeImap(become_seen=True)
    with _mail(settings_factory, fake) as mail, pytest.raises(MessageBecameSeenError):
        mail.fetch_raw_peek(10)


def test_mark_seen_verifies_server_flags(settings_factory):
    fake = FakeImap()
    with _mail(settings_factory, fake) as mail:
        mail.mark_seen(10)
    assert br"\Seen" in fake.flags[10]


def test_mark_seen_failure_is_reported(settings_factory):
    fake = FakeImap(refuse_seen=True)
    with _mail(settings_factory, fake) as mail, pytest.raises(MarkSeenError):
        mail.mark_seen(10)
