"""
Secure Logging Module.
Sanitizes credentials, tokens, and private keys before writing to console and logs/automation.log.

The log file always lives in <offpage-automation>/logs/, whatever the current working
directory is (previously it followed the CWD, which scattered logs across folders).
LOG_LEVEL (from .env or the environment) controls the console level; default INFO.
"""

import logging
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"

_SENSITIVE_PATTERNS = [
    (re.compile(r'(private_key["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(password["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(client_secret["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(bearer\s+)([A-Za-z0-9_\-\.]+)', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.DOTALL), '***REDACTED KEY***'),
]


class SanitizedFormatter(logging.Formatter):
    """Redacts credentials and secrets from log messages. Timestamps are IST."""

    def formatTime(self, record, datefmt=None):
        from datetime import datetime
        from .time_utils import IST
        return datetime.fromtimestamp(record.created, IST).strftime(datefmt or "%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        sanitized = super().format(record)
        for pat, repl in _SENSITIVE_PATTERNS:
            sanitized = pat.sub(repl, sanitized)
        return sanitized


def setup_logger(name: str = "ia_spaces_seo", log_dir=None) -> logging.Logger:
    """Configures and returns a logger writing to console and logs/automation.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    console_level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = SanitizedFormatter(
        "[%(asctime)s IST] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    p_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    try:
        p_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(p_dir / "automation.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except OSError:
        logger.warning("Could not open log file in %s; logging to console only.", p_dir)

    return logger


# Alias for convenience
get_logger = setup_logger
