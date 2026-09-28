from __future__ import annotations

import os
from pathlib import Path


def read_local_secret(
    repository_root: str | Path,
    name: str,
) -> str | None:
    """Read one secret from the process environment or an ignored .env.local."""
    environment_value = os.environ.get(name)
    if environment_value and environment_value.strip():
        return environment_value.strip()

    path = Path(repository_root) / ".env.local"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value or None

    return None
