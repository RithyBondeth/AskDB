"""Log output for the `askdb` loggers: plain text or one JSON object per line.

Events carry their fields in `extra={"fields": {...}}`, so the JSON form keeps
them as keys and the text form prints them as `key=value` after the message.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys

from askdb.config import Settings


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "fields", {})
        pairs = " ".join(f"{k}={_text(v)}" for k, v in fields.items() if v is not None)
        line = f"{self.formatTime(record)} {record.levelname} {record.name} {record.getMessage()}"
        line = f"{line} {pairs}" if pairs else line
        return f"{line}\n{self.formatException(record.exc_info)}" if record.exc_info else line


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = dt.datetime.fromtimestamp(record.created, dt.UTC)
        out = {
            "ts": ts.isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        out.update({k: v for k, v in getattr(record, "fields", {}).items() if v is not None})
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def _text(value: object) -> str:
    text = str(value)
    return json.dumps(text) if (" " in text or not text) else text


def configure(settings: Settings) -> None:
    """Send the `askdb` loggers to stderr in the configured format. Safe to call
    more than once: the handler is replaced, not added again."""
    logger = logging.getLogger("askdb")
    for h in [h for h in logger.handlers if getattr(h, "_askdb", False)]:
        logger.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter() if settings.log_format == "json" else _TextFormatter())
    handler._askdb = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False


def event(logger: logging.Logger, name: str, level: int = logging.INFO, **fields: object) -> None:
    logger.log(level, name, extra={"fields": fields})
