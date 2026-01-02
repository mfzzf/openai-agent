from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent.parent
_LOADED_ENV_PATH: Optional[Path] = None


def _parse_env_line(line: str) -> Optional[Tuple[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    if not key:
        return None
    return key, value


def _load_env_file(path: Path) -> None:
    try:
        content = path.read_text()
    except OSError:
        return
    for line in content.splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ[key] = value


def _maybe_disable_tracing(base_url: str) -> None:
    if os.getenv("OPENAI_AGENTS_DISABLE_TRACING") is not None:
        return
    trace_mode = (os.getenv("CHATKIT_TRACE_MODE") or "").strip().lower()
    if trace_mode == "otel":
        return
    host = urlparse(base_url).hostname or ""
    if not host.endswith("openai.com"):
        os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"


def _bootstrap_env() -> None:
    global _LOADED_ENV_PATH
    env_path = os.getenv("CHATKIT_ENV_FILE")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(REPO_ROOT / "apps" / "web" / ".env.local")
    candidates.append(ROOT / ".env.local")
    for path in candidates:
        if path.exists():
            _load_env_file(path)
            _LOADED_ENV_PATH = path
            break

    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ["OPENAI_API_BASE"] = base_url
        _maybe_disable_tracing(base_url)


_bootstrap_env()

DEFAULT_MODEL = "gpt-5.2"
DEFAULT_INSTRUCTIONS = (
    "You are an agent powering a workspace with a desktop and python panel.\n"
    "Use sandbox_desktop_start to open a desktop when needed, and sandbox_python_run for code.\n"
    "Use ui_open_tab to switch panels, ui_notify for status updates."
)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _is_truthy(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _tool_output_mode() -> str:
    mode = (_env("CHATKIT_TOOL_OUTPUT_MODE", "auto") or "auto").lower()
    if mode not in {"auto", "function", "text"}:
        mode = "auto"
    if mode == "auto":
        base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or ""
        if not base_url:
            return "function"
        host = urlparse(base_url).hostname or ""
        return "function" if host.endswith("openai.com") else "text"
    return mode


def _store_mode() -> str:
    mode = (_env("CHATKIT_STORE", "sqlite") or "sqlite").strip().lower()
    if mode in {"memory", "mem", "inmemory", "in-memory"}:
        return "memory"
    return "sqlite"


def _sqlite_path() -> Path:
    raw = _env("CHATKIT_SQLITE_PATH")
    if raw:
        return Path(raw).expanduser()
    return ROOT / "data" / "chatkit.sqlite"


def loaded_env_path() -> Optional[Path]:
    return _LOADED_ENV_PATH
