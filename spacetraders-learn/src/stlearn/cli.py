from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from stlearn.bot.loop import run_bootstrap_loop
from stlearn.client import SpaceTradersClient
from stlearn.config import get_settings
from stlearn.ingest.pipeline import ingest_agent_state, ingest_public_catalog
from stlearn.warehouse.db import init_db

app = typer.Typer(add_completion=False, no_args_is_help=True, help="SpaceTraders: ingest data and play to win.")
console = Console()


def _client(token: str | None = None) -> SpaceTradersClient:
    settings = get_settings()
    return SpaceTradersClient(settings.api_base, token if token is not None else settings.spacetraders_token or None)


@app.command("status")
def status_cmd() -> None:
    """Hit the public status endpoint."""
    with _client(token="") as client:
        # status is at API root; client prefixes /v2 already via base
        payload = client.get("/")
    console.print_json(data=payload)


@app.command("register")
def register_cmd(
    symbol: Optional[str] = typer.Option(None, help="Agent callsign (3-14 chars)"),
    faction: Optional[str] = typer.Option(None, help="Starting faction, e.g. COSMIC"),
) -> None:
    """Register a new agent using your account token from my.spacetraders.io."""
    settings = get_settings()
    account = settings.spacetraders_account_token
    if not account:
        console.print(
            "[red]Missing SPACETRADERS_ACCOUNT_TOKEN.[/]\n"
            "1. Create an account at https://my.spacetraders.io\n"
            "2. Copy your account token into .env as SPACETRADERS_ACCOUNT_TOKEN\n"
            "3. Re-run: stlearn register"
        )
        raise typer.Exit(code=1)

    body = {
        "symbol": (symbol or settings.spacetraders_symbol).upper(),
        "faction": (faction or settings.spacetraders_faction).upper(),
    }
    with SpaceTradersClient(settings.api_base, account) as client:
        payload = client.post("/register", json=body)

    token = (payload.get("data") or {}).get("token")
    agent = (payload.get("data") or {}).get("agent")
    console.print_json(data={"agent": agent, "token_preview": (token or "")[:18] + "..."})

    env_path = Path(".env")
    if token:
        _upsert_env(env_path, "SPACETRADERS_TOKEN", token)
        console.print(f"[green]Wrote SPACETRADERS_TOKEN to {env_path}[/]")


@app.command("ingest-catalog")
def ingest_catalog_cmd(
    pages: int = typer.Option(3, help="How many system pages to pull (20 systems/page)"),
) -> None:
    """Public ETL: systems → raw JSON → SQLite dims. No token required."""
    settings = get_settings()
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    with _client(token="") as client:
        counts = ingest_public_catalog(client, settings.raw_dir, settings.stlearn_db_path, max_pages=pages)
    console.print(counts)


@app.command("ingest")
def ingest_cmd() -> None:
    """Private ETL: agent, ships, contracts, HQ markets → warehouse."""
    settings = get_settings()
    if not settings.spacetraders_token:
        console.print("[red]Set SPACETRADERS_TOKEN in .env first (or run stlearn register).[/]")
        raise typer.Exit(code=1)
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        counts = ingest_agent_state(client, settings.raw_dir, settings.stlearn_db_path)
    console.print(counts)


@app.command("play")
def play_cmd(
    cycles: int = typer.Option(1, min=1, help="Mine/sell/deliver cycles"),
    also_ingest: bool = typer.Option(True, help="Snapshot warehouse before and after"),
) -> None:
    """Run the bootstrap bot loop (accept contract, mine, sell, deliver)."""
    settings = get_settings()
    if not settings.spacetraders_token:
        console.print("[red]Set SPACETRADERS_TOKEN in .env first.[/]")
        raise typer.Exit(code=1)
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        if also_ingest:
            console.rule("pre-ingest")
            console.print(ingest_agent_state(client, settings.raw_dir, settings.stlearn_db_path))
        run_bootstrap_loop(client, cycles=cycles)
        if also_ingest:
            console.rule("post-ingest")
            console.print(ingest_agent_state(client, settings.raw_dir, settings.stlearn_db_path))


@app.command("query")
def query_cmd(sql: str = typer.Argument("SELECT source, status, rows_loaded, started_at FROM etl_runs ORDER BY run_id DESC LIMIT 10")) -> None:
    """Run a read-only SQL query against the local warehouse."""
    settings = get_settings()
    conn = init_db(settings.stlearn_db_path)
    rows = conn.execute(sql).fetchall()
    if not rows:
        console.print("(no rows)")
        conn.close()
        return
    table = Table(show_header=True, header_style="bold")
    for key in rows[0].keys():
        table.add_column(key)
    for row in rows:
        table.add_row(*[str(row[k]) if row[k] is not None else "" for k in row.keys()])
    console.print(table)
    conn.close()


@app.command("report")
def report_cmd() -> None:
    """Show a quick warehouse summary for learning checkpoints."""
    settings = get_settings()
    conn = init_db(settings.stlearn_db_path)
    checks = {
        "systems": "SELECT COUNT(*) AS n FROM dim_system",
        "waypoints": "SELECT COUNT(*) AS n FROM dim_waypoint",
        "market_ticks": "SELECT COUNT(*) AS n FROM fact_market_price",
        "ship_snapshots": "SELECT COUNT(*) AS n FROM fact_ship_snapshot",
        "agent_snapshots": "SELECT COUNT(*) AS n FROM fact_agent_snapshot",
        "etl_runs": "SELECT COUNT(*) AS n FROM etl_runs",
    }
    summary = {name: conn.execute(sql).fetchone()["n"] for name, sql in checks.items()}
    latest = conn.execute(
        "SELECT agent_symbol, credits, observed_at FROM fact_agent_snapshot ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    console.print(summary)
    if latest:
        console.print(dict(latest))


def _upsert_env(path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if path.exists():
        lines = path.read_text().splitlines()
    found = False
    out: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    app()
