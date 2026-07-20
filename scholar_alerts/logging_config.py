from __future__ import annotations

import logging
import re


def configure_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def masked_sender(sender: str) -> str:
    """Retain enough of a sender for diagnostics without logging a recipient address."""
    match = re.fullmatch(r"([^@]+)@(.+)", sender.strip())
    if not match:
        return "<invalid>"
    local, domain = match.groups()
    visible = local[:3]
    return f"{visible}***@{domain}"

