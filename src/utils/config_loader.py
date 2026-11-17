"""
Configuration loader.

- YAML: uses PyYAML when installed; falls back to a lightweight built-in parser.
- .env: a small dependency-free loader (KEY=VALUE lines). Values already present in
  the process environment win, so GitHub Actions secrets/env always take precedence.
- load_settings(): settings.yaml with documented .env / environment overrides applied.
"""

import os
from pathlib import Path
from typing import Any, Dict


def _simple_yaml_parse(content: str) -> Dict[str, Any]:
    """Lightweight pure-python parser for basic YAML key-value and list structures."""
    result: Dict[str, Any] = {}
    current_key = None
    stack = [(0, result)]

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()

        current_dict = stack[-1][1]

        if stripped.startswith("- "):
            val = stripped[2:].strip().strip('"').strip("'")
            if isinstance(current_key, str) and current_key in current_dict:
                if not isinstance(current_dict[current_key], list):
                    current_dict[current_key] = []
                current_dict[current_key].append(val)
            continue

        if ":" in stripped:
            key, val = (p.strip() for p in stripped.split(":", 1))
            current_key = key
            if val == "":
                new_dict: Dict[str, Any] = {}
                current_dict[key] = new_dict
                stack.append((indent + 2, new_dict))
            else:
                clean_val = val.strip('"').strip("'")
                if clean_val.lower() == "true":
                    current_dict[key] = True
                elif clean_val.lower() == "false":
                    current_dict[key] = False
                elif clean_val.isdigit():
                    current_dict[key] = int(clean_val)
                else:
                    try:
                        current_dict[key] = float(clean_val)
                    except ValueError:
                        current_dict[key] = clean_val

    return result


def load_yaml(file_path) -> Dict[str, Any]:
    """Loads a YAML file using PyYAML if available, or the native fallback."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Configuration file not found: {p}")

    text = p.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _simple_yaml_parse(text)


# Alias kept for backwards compatibility
load_yaml_config = load_yaml


def load_env_file(env_path) -> Dict[str, str]:
    """Load KEY=VALUE pairs from a .env file into os.environ (existing values win).

    Returns the pairs that were read from the file. Missing file -> {}.
    """
    p = Path(env_path)
    loaded: Dict[str, str] = {}
    if not p.is_file():
        return loaded

    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def _env_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_settings(base_dir) -> Dict[str, Any]:
    """Load config/settings.yaml and apply environment overrides.

    Supported overrides (from .env or the process environment):
      USER_AGENT, REQUEST_TIMEOUT_SECONDS, REQUEST_DELAY_SECONDS, MAX_RETRIES,
      GOOGLE_SHEET_NAME, GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_FILE, REQUIRE_SHEETS
    """
    base = Path(base_dir)
    load_env_file(base / ".env")
    settings = load_yaml(base / "config" / "settings.yaml")

    crawler = settings.setdefault("crawler", {})
    sheets = settings.setdefault("sheets", {})
    env = os.environ

    if env.get("USER_AGENT"):
        crawler["user_agent"] = env["USER_AGENT"]
    if env.get("REQUEST_TIMEOUT_SECONDS"):
        crawler["timeout_seconds"] = float(env["REQUEST_TIMEOUT_SECONDS"])
    if env.get("REQUEST_DELAY_SECONDS"):
        crawler["request_delay_seconds"] = float(env["REQUEST_DELAY_SECONDS"])
    if env.get("MAX_RETRIES"):
        crawler["max_retries"] = int(env["MAX_RETRIES"])
    if env.get("GOOGLE_SHEET_NAME"):
        sheets["sheet_name"] = env["GOOGLE_SHEET_NAME"]
    if env.get("GOOGLE_SHEET_ID"):
        sheets["sheet_id"] = env["GOOGLE_SHEET_ID"]
    if env.get("GOOGLE_SERVICE_ACCOUNT_FILE"):
        sheets["service_account_path"] = env["GOOGLE_SERVICE_ACCOUNT_FILE"]
    if env.get("REQUIRE_SHEETS"):
        sheets["require_connection"] = _env_bool(env["REQUIRE_SHEETS"])

    return settings


def resolve_path(base_dir, path_value: str) -> str:
    """Resolve a config path relative to the project root unless already absolute."""
    if not path_value:
        return ""
    p = Path(path_value)
    return str(p if p.is_absolute() else Path(base_dir) / p)
