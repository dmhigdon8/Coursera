"""Raw landing zone: write every API payload as JSON before transforming.

This mirrors production patterns (S3/GCS landing zone) at laptop scale.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def write_raw(raw_dir: Path, source: str, payload: Any, *, stamp: str | None = None) -> Path:
    stamp = stamp or utc_now().replace(":", "").replace(".", "")
    safe_source = source.strip("/").replace("/", "__")
    out_dir = raw_dir / safe_source
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path
