"""Extractors: pull from SpaceTraders API into the raw landing zone + memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from stlearn.client import SpaceTradersClient
from stlearn.ingest.raw import utc_now, write_raw
from pathlib import Path


@dataclass
class ExtractResult:
    source: str
    observed_at: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    raw_paths: list[str] = field(default_factory=list)


def extract_systems(
    client: SpaceTradersClient,
    raw_dir: Path,
    *,
    max_pages: int | None = 5,
    limit: int = 20,
) -> ExtractResult:
    """Public catalog extract — works without a token."""
    observed_at = utc_now()
    rows = list(client.paginate("/systems", limit=limit, max_pages=max_pages))
    path = write_raw(raw_dir, "systems", {"observed_at": observed_at, "data": rows}, stamp=_stamp(observed_at))
    return ExtractResult(source="systems", observed_at=observed_at, rows=rows, raw_paths=[str(path)])


def extract_system_waypoints(
    client: SpaceTradersClient,
    raw_dir: Path,
    system_symbol: str,
) -> ExtractResult:
    observed_at = utc_now()
    rows = list(client.paginate(f"/systems/{system_symbol}/waypoints", limit=20))
    path = write_raw(
        raw_dir,
        f"waypoints/{system_symbol}",
        {"observed_at": observed_at, "system": system_symbol, "data": rows},
        stamp=_stamp(observed_at),
    )
    return ExtractResult(source=f"waypoints:{system_symbol}", observed_at=observed_at, rows=rows, raw_paths=[str(path)])


def extract_market(
    client: SpaceTradersClient,
    raw_dir: Path,
    system_symbol: str,
    waypoint_symbol: str,
) -> ExtractResult:
    observed_at = utc_now()
    payload = client.get(f"/systems/{system_symbol}/waypoints/{waypoint_symbol}/market")
    path = write_raw(
        raw_dir,
        f"markets/{waypoint_symbol}",
        {"observed_at": observed_at, "data": payload.get("data", payload)},
        stamp=_stamp(observed_at),
    )
    market = payload.get("data") or {}
    return ExtractResult(
        source=f"market:{waypoint_symbol}",
        observed_at=observed_at,
        rows=[market],
        raw_paths=[str(path)],
    )


def extract_agent(client: SpaceTradersClient, raw_dir: Path) -> ExtractResult:
    observed_at = utc_now()
    payload = client.get("/my/agent")
    agent = payload.get("data") or {}
    path = write_raw(raw_dir, "agent", {"observed_at": observed_at, "data": agent}, stamp=_stamp(observed_at))
    return ExtractResult(source="agent", observed_at=observed_at, rows=[agent], raw_paths=[str(path)])


def extract_ships(client: SpaceTradersClient, raw_dir: Path) -> ExtractResult:
    observed_at = utc_now()
    rows = list(client.paginate("/my/ships", limit=20))
    path = write_raw(raw_dir, "ships", {"observed_at": observed_at, "data": rows}, stamp=_stamp(observed_at))
    return ExtractResult(source="ships", observed_at=observed_at, rows=rows, raw_paths=[str(path)])


def extract_contracts(client: SpaceTradersClient, raw_dir: Path) -> ExtractResult:
    observed_at = utc_now()
    rows = list(client.paginate("/my/contracts", limit=20))
    path = write_raw(raw_dir, "contracts", {"observed_at": observed_at, "data": rows}, stamp=_stamp(observed_at))
    return ExtractResult(source="contracts", observed_at=observed_at, rows=rows, raw_paths=[str(path)])


def _stamp(observed_at: str) -> str:
    return observed_at.replace(":", "").replace(".", "")
