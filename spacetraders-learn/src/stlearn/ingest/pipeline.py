from __future__ import annotations

from pathlib import Path

from stlearn.client import SpaceTradersClient
from stlearn.ingest import extract, load
from stlearn.warehouse.db import init_db


def ingest_public_catalog(
    client: SpaceTradersClient,
    raw_dir: Path,
    db_path: Path,
    *,
    max_pages: int = 3,
) -> dict[str, int]:
    """Learn path step 1: public systems extract → dims (no token needed)."""
    conn = init_db(db_path)
    systems = extract.extract_systems(client, raw_dir, max_pages=max_pages)
    loaded = load.run_load(conn, systems, "load_systems", load.load_systems)
    conn.close()
    return {"systems_extracted": len(systems.rows), "systems_loaded": loaded}


def ingest_agent_state(
    client: SpaceTradersClient,
    raw_dir: Path,
    db_path: Path,
) -> dict[str, int]:
    """Learn path step 2: private agent/ships/contracts snapshots."""
    conn = init_db(db_path)
    counts: dict[str, int] = {}

    agent = extract.extract_agent(client, raw_dir)
    counts["agent"] = load.run_load(conn, agent, "load_agent", load.load_agent)

    ships = extract.extract_ships(client, raw_dir)
    counts["ships"] = load.run_load(conn, ships, "load_ships", load.load_ships)

    contracts = extract.extract_contracts(client, raw_dir)
    counts["contracts"] = load.run_load(conn, contracts, "load_contracts", load.load_contracts)

    # Enrich HQ system waypoints for later market/mining logic.
    hq = (agent.rows[0] or {}).get("headquarters") if agent.rows else None
    if hq:
        system_symbol = "-".join(hq.split("-")[:2])
        wps = extract.extract_system_waypoints(client, raw_dir, system_symbol)
        # Ensure parent system exists for FK.
        if not conn.execute("SELECT 1 FROM dim_system WHERE system_symbol = ?", (system_symbol,)).fetchone():
            stub = extract.ExtractResult(
                source=f"system-stub:{system_symbol}",
                observed_at=wps.observed_at,
                rows=[{"symbol": system_symbol, "waypoints": []}],
            )
            load.load_systems(conn, stub)
        counts["waypoints"] = load.run_load(
            conn,
            wps,
            "load_waypoints",
            load.load_waypoints,
            system_symbol=system_symbol,
        )

        market_loaded = 0
        for wp in wps.rows:
            traits = {t.get("symbol") for t in (wp.get("traits") or [])}
            if "MARKETPLACE" not in traits:
                continue
            market = extract.extract_market(client, raw_dir, system_symbol, wp["symbol"])
            # Markets without a ship present may omit tradeGoods — still store raw.
            market_loaded += load.run_load(conn, market, "load_market", load.load_market)
        counts["markets"] = market_loaded

    conn.close()
    return counts
