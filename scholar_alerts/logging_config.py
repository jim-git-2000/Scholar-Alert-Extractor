from __future__ import annotations

import logging
import re
import shlex
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
OUTPUT_LOGGER_NAME = "scholar_alerts.command_output"
_HANDLER_MARKER = "_scholar_alerts_handler"


def _remove_our_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()


def _marked(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _HANDLER_MARKER, True)
    return handler


def configure_logging(
    level: str = "INFO",
    *,
    log_file: Path | None = None,
    command: list[str] | None = None,
) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    _remove_our_handlers(root_logger)

    if not root_logger.handlers:
        console_handler = _marked(logging.StreamHandler())
        console_handler.setFormatter(formatter)
        console_handler.setLevel(numeric_level)
        root_logger.addHandler(console_handler)

    output_logger = logging.getLogger(OUTPUT_LOGGER_NAME)
    output_logger.setLevel(logging.INFO)
    output_logger.propagate = False
    _remove_our_handlers(output_logger)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        root_file_handler = _marked(logging.FileHandler(log_file, encoding="utf-8"))
        root_file_handler.setFormatter(formatter)
        root_file_handler.setLevel(numeric_level)
        root_logger.addHandler(root_file_handler)

        output_file_handler = _marked(logging.FileHandler(log_file, encoding="utf-8"))
        output_file_handler.setFormatter(formatter)
        output_file_handler.setLevel(logging.INFO)
        output_logger.addHandler(output_file_handler)

    args = command if command is not None else sys.argv
    rendered_command = " ".join(shlex.quote(str(item)) for item in args)
    record_cli_output(f"RUN_START command={rendered_command}")


def close_logging() -> None:
    _remove_our_handlers(logging.getLogger())
    _remove_our_handlers(logging.getLogger(OUTPUT_LOGGER_NAME))


def record_cli_output(message: str, *, error: bool = False) -> None:
    logger = logging.getLogger(OUTPUT_LOGGER_NAME)
    if error:
        logger.error(message)
    else:
        logger.info(message)


def masked_sender(sender: str) -> str:
    """Retain enough of a sender for diagnostics without logging a recipient address."""
    match = re.fullmatch(r"([^@]+)@(.+)", sender.strip())
    if not match:
        return "<invalid>"
    local, domain = match.groups()
    visible = local[:3]
    return f"{visible}***@{domain}"
