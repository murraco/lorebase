import json
import logging


class JSONFormatter(logging.Formatter):
    """One JSON object per line -- easy for any log aggregator to parse
    without needing to understand Django's default human-readable format.
    Only used in prod (see settings/prod.py): dev keeps Django's default
    formatting, since there's no aggregator to feed locally and JSON is
    harder to scan in a raw terminal.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)
