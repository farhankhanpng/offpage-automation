"""
Secure Logging Module.
Sanitizes credentials, tokens, and private keys before writing to console and logs/automation.log.
"""

import logging
import re
from pathlib import Path

_SENSITIVE_PATTERNS = [
    (re.compile(r'(private_key["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(password["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(client_secret["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE), r'\1***REDACTED***\3'),
    (re.compile(r'(bearer\s+)([A-Za-z0-9_\-\.]+)', re.IGNORECASE), r'\1***REDACTED***'),
]

class SanitizedFormatter(logging.Formatter):
    """Redacts credentials and secrets from log messages."""
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        sanitized = original
        for pat, repl in _SENSITIVE_PATTERNS:
            sanitized = pat.sub(repl, sanitized)
        return sanitized

def setup_logger(name: str = "ia_spaces_seo", log_dir: str | Path = "logs") -> logging.Logger:
    """Configures and returns the central system logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    formatter = SanitizedFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler
    p_dir = Path(log_dir)
    p_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(p_dir / "automation.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

# Alias for convenience
get_logger = setup_logger
