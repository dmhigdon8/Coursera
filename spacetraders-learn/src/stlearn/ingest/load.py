"""Transform + load nested API JSON into warehouse tables."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from stlearn.ingest.extract import ExtractResult
from stlearn.ingest.raw import utc_now


def start_run(conn: sqlite3.Connection, source: str) -> int:
    cur = conn.execute(
        "INSERT INTO etl_runs (started_at, source, status) VALUES (?, ?, ?)",
        (utc_now(), source, "running"),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    rows_extracted: int = 0,
    rows_loaded: int = 0,
    notes: str = "",
) -> None:
    conn.execute(
        """
        UPDATE etl_runs
        SET finished_at = ?, status = ?, rows_extracted = ?, rows_loaded = ?, notes = ?
        WHERE run_id = ?
        """,
        (utc_now(), status, rows_extracted, rows_loaded, notes, run_id),
    )
    conn.commit()


def load_systems(conn: sqlite3.Connection, result: ExtractResult) -> int:
    loaded = 0
    for row in result.rows:
        conn.execute(
            """
            INSERT INTO dim_system (system_symbol, sector_symbol, type, x, y, name, constellation, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(system_symbol) DO UPDATE SET
                sector_symbol=excluded.sector_symbol,
                type=excluded.type,
                x=excluded.x,
                y=excluded.y,
                name=excluded.name,
                constellation=excluded.constellation,
                ingested_at=excluded.ingested_at
            """,
            (
                row.get("symbol"),
                row.get("sectorSymbol"),
                row.get("type"),
                row.get("x"),
                row.get("y"),
                row.get("name"),
                row.get("constellation"),
                result.observed_at,
            ),
        )
        for wp in row.get("waypoints") or []:
            conn.execute(
                """
                INSERT INTO dim_waypoint (
                    waypoint_symbol, system_symbol, type, x, y, orbits, traits_json, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(waypoint_symbol) DO UPDATE SET
                    system_symbol=excluded.system_symbol,
                    type=excluded.type,
                    x=excluded.x,
                    y=excluded.y,
                    orbits=excluded.orbits,
                    traits_json=COALESCE(excluded.traits_json, dim_waypoint.traits_json),
                    ingested_at=excluded.ingested_at
                """,
                (
                    wp.get("symbol"),
                    row.get("symbol"),
                    wp.get("type"),
                    wp.get("x"),
                    wp.get("y"),
                    (wp.get("orbitals") or [{}])[0].get("symbol") if wp.get("orbitals") else wp.get("orbits"),
                    None,
                    result.observed_at,
                ),
            )
        loaded += 1
    conn.commit()
    return loaded


def load_waypoints(conn: sqlite3.Connection, result: ExtractResult, system_symbol: str) -> int:
    loaded = 0
    for wp in result.rows:
        traits = wp.get("traits") or []
        conn.execute(
            """
            INSERT INTO dim_waypoint (
                waypoint_symbol, system_symbol, type, x, y, orbits, traits_json, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(waypoint_symbol) DO UPDATE SET
                type=excluded.type,
                x=excluded.x,
                y=excluded.y,
                orbits=excluded.orbits,
                traits_json=excluded.traits_json,
                ingested_at=excluded.ingested_at
            """,
            (
                wp.get("symbol"),
                system_symbol,
                wp.get("type"),
                wp.get("x"),
                wp.get("y"),
                wp.get("orbits"),
                json.dumps(traits),
                result.observed_at,
            ),
        )
        loaded += 1
    conn.commit()
    return loaded


def load_market(conn: sqlite3.Connection, result: ExtractResult) -> int:
    if not result.rows:
        return 0
    market = result.rows[0]
    waypoint = market.get("symbol")
    system_symbol = "-".join(waypoint.split("-")[:2]) if waypoint else ""
    loaded = 0
    for good in market.get("tradeGoods") or []:
        trade_symbol = good.get("symbol")
        conn.execute(
            """
            INSERT INTO dim_good (trade_symbol, name, ingested_at)
            VALUES (?, ?, ?)
            ON CONFLICT(trade_symbol) DO UPDATE SET ingested_at=excluded.ingested_at
            """,
            (trade_symbol, trade_symbol, result.observed_at),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO fact_market_price (
                observed_at, system_symbol, waypoint_symbol, trade_symbol,
                supply, activity, purchase_price, sell_price, trade_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.observed_at,
                system_symbol,
                waypoint,
                trade_symbol,
                good.get("supply"),
                good.get("activity"),
                good.get("purchasePrice"),
                good.get("sellPrice"),
                good.get("tradeVolume"),
            ),
        )
        loaded += 1
    conn.commit()
    return loaded


def load_agent(conn: sqlite3.Connection, result: ExtractResult) -> int:
    if not result.rows:
        return 0
    agent = result.rows[0]
    conn.execute(
        """
        INSERT OR IGNORE INTO fact_agent_snapshot (
            observed_at, agent_symbol, headquarters, credits, ship_count, starting_faction
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            result.observed_at,
            agent.get("symbol"),
            agent.get("headquarters"),
            agent.get("credits"),
            agent.get("shipCount"),
            agent.get("startingFaction"),
        ),
    )
    conn.commit()
    return 1


def load_ships(conn: sqlite3.Connection, result: ExtractResult) -> int:
    loaded = 0
    for ship in result.rows:
        nav = ship.get("nav") or {}
        route = nav.get("route") or {}
        fuel = ship.get("fuel") or {}
        cargo = ship.get("cargo") or {}
        frame = (ship.get("frame") or {}).get("symbol")
        conn.execute(
            """
            INSERT OR IGNORE INTO fact_ship_snapshot (
                observed_at, ship_symbol, role, system_symbol, waypoint_symbol,
                status, flight_mode, fuel_current, fuel_capacity,
                cargo_units, cargo_capacity, cargo_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.observed_at,
                ship.get("symbol"),
                frame,
                nav.get("systemSymbol") or route.get("systemSymbol"),
                nav.get("waypointSymbol"),
                nav.get("status"),
                nav.get("flightMode"),
                fuel.get("current"),
                fuel.get("capacity"),
                cargo.get("units"),
                cargo.get("capacity"),
                json.dumps(cargo.get("inventory") or []),
            ),
        )
        loaded += 1
    conn.commit()
    return loaded


def load_contracts(conn: sqlite3.Connection, result: ExtractResult) -> int:
    loaded = 0
    for contract in result.rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO fact_contract_event (
                observed_at, contract_id, faction_symbol, type, accepted, fulfilled,
                deadline_to_accept, expiration, terms_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.observed_at,
                contract.get("id"),
                contract.get("factionSymbol"),
                contract.get("type"),
                1 if contract.get("accepted") else 0,
                1 if contract.get("fulfilled") else 0,
                contract.get("deadlineToAccept"),
                (contract.get("terms") or {}).get("deadline"),
                json.dumps(contract.get("terms") or {}),
            ),
        )
        loaded += 1
    conn.commit()
    return loaded


def run_load(conn: sqlite3.Connection, result: ExtractResult, loader_name: str, loader_fn: Any, **kwargs: Any) -> int:
    run_id = start_run(conn, result.source)
    try:
        loaded = loader_fn(conn, result, **kwargs) if kwargs else loader_fn(conn, result)
        finish_run(
            conn,
            run_id,
            status="success",
            rows_extracted=len(result.rows),
            rows_loaded=loaded,
            notes=loader_name,
        )
        return loaded
    except Exception as exc:  # noqa: BLE001 - surface into etl_runs
        finish_run(conn, run_id, status="failed", rows_extracted=len(result.rows), notes=str(exc))
        raise
