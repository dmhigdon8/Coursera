-- SpaceTraders learning warehouse (SQLite)
-- Pattern: raw JSON landing zone on disk + typed tables here.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS etl_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    rows_extracted INTEGER DEFAULT 0,
    rows_loaded INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS dim_system (
    system_symbol TEXT PRIMARY KEY,
    sector_symbol TEXT,
    type TEXT,
    x INTEGER,
    y INTEGER,
    name TEXT,
    constellation TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_waypoint (
    waypoint_symbol TEXT PRIMARY KEY,
    system_symbol TEXT NOT NULL,
    type TEXT,
    x INTEGER,
    y INTEGER,
    orbits TEXT,
    traits_json TEXT,
    ingested_at TEXT NOT NULL,
    FOREIGN KEY (system_symbol) REFERENCES dim_system(system_symbol)
);

CREATE TABLE IF NOT EXISTS dim_good (
    trade_symbol TEXT PRIMARY KEY,
    name TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_market_price (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    system_symbol TEXT NOT NULL,
    waypoint_symbol TEXT NOT NULL,
    trade_symbol TEXT NOT NULL,
    supply TEXT,
    activity TEXT,
    purchase_price INTEGER,
    sell_price INTEGER,
    trade_volume INTEGER,
    UNIQUE (observed_at, waypoint_symbol, trade_symbol)
);

CREATE TABLE IF NOT EXISTS fact_ship_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    ship_symbol TEXT NOT NULL,
    role TEXT,
    system_symbol TEXT,
    waypoint_symbol TEXT,
    status TEXT,
    flight_mode TEXT,
    fuel_current INTEGER,
    fuel_capacity INTEGER,
    cargo_units INTEGER,
    cargo_capacity INTEGER,
    cargo_json TEXT,
    UNIQUE (observed_at, ship_symbol)
);

CREATE TABLE IF NOT EXISTS fact_agent_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    agent_symbol TEXT NOT NULL,
    headquarters TEXT,
    credits INTEGER,
    ship_count INTEGER,
    starting_faction TEXT,
    UNIQUE (observed_at, agent_symbol)
);

CREATE TABLE IF NOT EXISTS fact_contract_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    contract_id TEXT NOT NULL,
    faction_symbol TEXT,
    type TEXT,
    accepted INTEGER,
    fulfilled INTEGER,
    deadline_to_accept TEXT,
    expiration TEXT,
    terms_json TEXT,
    UNIQUE (observed_at, contract_id)
);

CREATE INDEX IF NOT EXISTS idx_market_waypoint_time
    ON fact_market_price (waypoint_symbol, observed_at);
CREATE INDEX IF NOT EXISTS idx_ship_time
    ON fact_ship_snapshot (ship_symbol, observed_at);
CREATE INDEX IF NOT EXISTS idx_agent_time
    ON fact_agent_snapshot (agent_symbol, observed_at);
