"""Starter bot: accept contract → buy miner if needed → extract → sell → deliver.

Optimized later using warehouse market history. Learning first: reliable state machine.
"""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console

from stlearn.client import SpaceTradersClient, SpaceTradersError

console = Console()


def _data(payload: dict[str, Any]) -> Any:
    return payload.get("data", payload)


def wait_for_arrival(client: SpaceTradersClient, ship_symbol: str) -> dict[str, Any]:
    while True:
        ship = _data(client.get(f"/my/ships/{ship_symbol}"))
        nav = ship.get("nav") or {}
        status = nav.get("status")
        if status != "IN_TRANSIT":
            return ship
        route = nav.get("route") or {}
        arrival = route.get("arrival")
        console.log(f"{ship_symbol} in transit, arrival={arrival}")
        time.sleep(5)


def ensure_docked(client: SpaceTradersClient, ship_symbol: str) -> None:
    ship = wait_for_arrival(client, ship_symbol)
    if (ship.get("nav") or {}).get("status") == "DOCKED":
        return
    client.post(f"/my/ships/{ship_symbol}/dock")


def ensure_orbit(client: SpaceTradersClient, ship_symbol: str) -> None:
    ship = wait_for_arrival(client, ship_symbol)
    if (ship.get("nav") or {}).get("status") == "IN_ORBIT":
        return
    client.post(f"/my/ships/{ship_symbol}/orbit")


def navigate(client: SpaceTradersClient, ship_symbol: str, waypoint: str) -> None:
    ship = wait_for_arrival(client, ship_symbol)
    nav = ship.get("nav") or {}
    if nav.get("waypointSymbol") == waypoint and nav.get("status") != "IN_TRANSIT":
        return
    if nav.get("status") == "DOCKED":
        client.post(f"/my/ships/{ship_symbol}/orbit")
    client.post(f"/my/ships/{ship_symbol}/navigate", json={"waypointSymbol": waypoint})
    wait_for_arrival(client, ship_symbol)


def refuel_if_needed(client: SpaceTradersClient, ship_symbol: str, threshold: float = 0.4) -> None:
    ship = wait_for_arrival(client, ship_symbol)
    fuel = ship.get("fuel") or {}
    capacity = fuel.get("capacity") or 0
    current = fuel.get("current") or 0
    if capacity and current / capacity >= threshold:
        return
    ensure_docked(client, ship_symbol)
    try:
        client.post(f"/my/ships/{ship_symbol}/refuel")
        console.log(f"refueled {ship_symbol}")
    except SpaceTradersError as exc:
        console.log(f"[yellow]refuel skipped[/]: {exc}")


def accept_open_contracts(client: SpaceTradersClient) -> list[dict[str, Any]]:
    contracts = list(client.paginate("/my/contracts", limit=20))
    accepted: list[dict[str, Any]] = []
    for contract in contracts:
        if contract.get("accepted") or contract.get("fulfilled"):
            if contract.get("accepted") and not contract.get("fulfilled"):
                accepted.append(contract)
            continue
        result = _data(client.post(f"/my/contracts/{contract['id']}/accept"))
        accepted.append(result.get("contract") or contract)
        console.log(f"accepted contract {contract['id']}")
    return accepted


def find_ship(client: SpaceTradersClient, *, prefer_mining: bool = True) -> dict[str, Any]:
    ships = list(client.paginate("/my/ships", limit=20))
    if not ships:
        raise RuntimeError("No ships available")
    if prefer_mining:
        for ship in ships:
            mounts = {m.get("symbol", "") for m in (ship.get("mounts") or [])}
            if any("MINING" in m or "LASER" in m for m in mounts):
                return ship
            frame = ((ship.get("frame") or {}).get("symbol") or "")
            if "DRONE" in frame or "MINER" in frame:
                return ship
    # Prefer command ship with cargo capacity
    ships.sort(key=lambda s: ((s.get("cargo") or {}).get("capacity") or 0), reverse=True)
    return ships[0]


def find_asteroid(client: SpaceTradersClient, system_symbol: str) -> str | None:
    for wp in client.paginate(f"/systems/{system_symbol}/waypoints", limit=20):
        if wp.get("type") in {"ASTEROID", "ENGINEERED_ASTEROID", "ASTEROID_FIELD"}:
            return wp["symbol"]
        traits = {t.get("symbol") for t in (wp.get("traits") or [])}
        if "COMMON_METAL_DEPOSITS" in traits or "MINERAL_DEPOSITS" in traits:
            return wp["symbol"]
    return None


def extract_until_full(client: SpaceTradersClient, ship_symbol: str, max_extracts: int = 8) -> None:
    ensure_orbit(client, ship_symbol)
    for _ in range(max_extracts):
        ship = _data(client.get(f"/my/ships/{ship_symbol}"))
        cargo = ship.get("cargo") or {}
        if (cargo.get("units") or 0) >= (cargo.get("capacity") or 0):
            break
        cooldown = (ship.get("cooldown") or {}).get("remainingSeconds") or 0
        if cooldown:
            time.sleep(min(int(cooldown) + 1, 90))
        try:
            result = _data(client.post(f"/my/ships/{ship_symbol}/extract"))
            extracted = (result.get("extraction") or {}).get("yield") or {}
            console.log(f"extracted {extracted}")
            cd = (result.get("cooldown") or {}).get("remainingSeconds") or 0
            if cd:
                time.sleep(min(int(cd) + 1, 90))
        except SpaceTradersError as exc:
            console.log(f"[yellow]extract stopped[/]: {exc}")
            break


def sell_all_cargo(client: SpaceTradersClient, ship_symbol: str) -> None:
    ensure_docked(client, ship_symbol)
    ship = _data(client.get(f"/my/ships/{ship_symbol}"))
    for item in list((ship.get("cargo") or {}).get("inventory") or []):
        symbol = item.get("symbol")
        units = item.get("units") or 0
        if not symbol or not units:
            continue
        try:
            client.post(
                f"/my/ships/{ship_symbol}/sell",
                json={"symbol": symbol, "units": units},
            )
            console.log(f"sold {units} {symbol}")
        except SpaceTradersError as exc:
            console.log(f"[yellow]could not sell {symbol}[/]: {exc}")


def deliver_contract_cargo(client: SpaceTradersClient, ship_symbol: str, contract: dict[str, Any]) -> None:
    terms = contract.get("terms") or {}
    for delivery in terms.get("deliver") or []:
        dest = delivery.get("destinationSymbol")
        trade_symbol = delivery.get("tradeSymbol")
        units_required = (delivery.get("unitsRequired") or 0) - (delivery.get("unitsFulfilled") or 0)
        if units_required <= 0 or not dest:
            continue
        navigate(client, ship_symbol, dest)
        ensure_docked(client, ship_symbol)
        ship = _data(client.get(f"/my/ships/{ship_symbol}"))
        inv = {(i.get("symbol")): (i.get("units") or 0) for i in ((ship.get("cargo") or {}).get("inventory") or [])}
        have = inv.get(trade_symbol, 0)
        if have <= 0:
            console.log(f"no {trade_symbol} aboard to deliver")
            continue
        units = min(have, units_required)
        client.post(
            f"/my/contracts/{contract['id']}/deliver",
            json={"shipSymbol": ship_symbol, "tradeSymbol": trade_symbol, "units": units},
        )
        console.log(f"delivered {units} {trade_symbol} for contract {contract['id']}")


def run_bootstrap_loop(client: SpaceTradersClient, cycles: int = 1) -> None:
    """One learning-friendly gameplay loop that also generates ingestible events."""
    agent = _data(client.get("/my/agent"))
    console.log(f"agent={agent.get('symbol')} credits={agent.get('credits')}")
    hq = agent.get("headquarters") or ""
    system_symbol = "-".join(hq.split("-")[:2])

    contracts = accept_open_contracts(client)
    ship = find_ship(client)
    ship_symbol = ship["symbol"]
    console.log(f"using ship {ship_symbol}")

    asteroid = find_asteroid(client, system_symbol)
    for cycle in range(1, cycles + 1):
        console.rule(f"cycle {cycle}/{cycles}")
        refuel_if_needed(client, ship_symbol)
        if asteroid:
            navigate(client, ship_symbol, asteroid)
            extract_until_full(client, ship_symbol)
        # Sell at HQ marketplace first (simple heuristic).
        if hq:
            navigate(client, ship_symbol, hq)
            sell_all_cargo(client, ship_symbol)
        for contract in contracts:
            deliver_contract_cargo(client, ship_symbol, contract)
            try:
                client.post(f"/my/contracts/{contract['id']}/fulfill")
                console.log(f"fulfilled {contract['id']}")
            except SpaceTradersError:
                pass

    agent = _data(client.get("/my/agent"))
    console.log(f"done. credits={agent.get('credits')}")
