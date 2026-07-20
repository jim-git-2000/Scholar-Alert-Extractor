from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from scholar_alerts.config import Settings, load_source_rules
from scholar_alerts.models import Paper


@pytest.fixture
def paper_factory():
    def make(**overrides):
        values = {
            "title": "Robust Direction Finding",
            "authors": ["Alice Zhang", "Bob Li"],
            "year": 2025,
            "publication": "IEEE Transactions on Signal Processing",
            "doi": "10.1109/TSP.2025.12345",
            "ieee_document_id": "12345678",
            "paper_url": "https://ieeexplore.ieee.org/document/12345678",
            "pdf_url": None,
            "snippet": "A robust method for direction finding.",
            "source": "ieee_author_alert",
            "alert_name": "Alice Zhang",
            "received_at": datetime(2026, 7, 1, 8, 30),
            "message_id": "<fixture@example.test>",
            "email_uid": 42,
        }
        values.update(overrides)
        return Paper(**values)

    return make


@pytest.fixture
def settings_factory(tmp_path: Path):
    def make(**overrides):
        values = {
            "imap_host": "imap.example.test",
            "imap_port": 993,
            "imap_username": "user@example.test",
            "imap_password": "secret-token",
            "target_folder": "Alerts",
            "output_file": tmp_path / "papers.xlsx",
            "imap_timeout_seconds": 30,
            "max_emails_per_run": 100,
            "log_level": "INFO",
            "source_rules": load_source_rules(Path("config/sources.yaml")),
        }
        values.update(overrides)
        return Settings(**values)

    return make
