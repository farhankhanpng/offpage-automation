"""
Configuration Loader with native fallback.
Supports PyYAML when installed; falls back to a lightweight built-in YAML parser.
"""

import os
from pathlib import Path
from typing import Any, Dict

def _simple_yaml_parse(content: str) -> Dict[str, Any]:
    """Lightweight pure-python parser for basic YAML key-value and list structures."""
    result: Dict[str, Any] = {}
    current_key = None
    lines = content.splitlines()
    
    current_section = result
    stack = [(0, result)]
    
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
            
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        while stack and indent < stack[-1][0]:
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
            parts = stripped.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            current_key = key
            
            if val == "":
                new_dict = {}
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

def load_yaml(file_path: str | Path) -> Dict[str, Any]:
    """Loads a YAML file using PyYAML if available, or native fallback."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Configuration file not found: {p}")
        
    text = p.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _simple_yaml_parse(text)

# Alias
load_yaml_config = load_yaml
