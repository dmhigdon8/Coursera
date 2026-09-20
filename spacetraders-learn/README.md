# SpaceTraders Learn

Learn **data ingestion** by playing [SpaceTraders](https://spacetraders.io) — an API-only space trading game. Winning is the motivator; the warehouse is the curriculum.

## What you build

```text
SpaceTraders API
      │
      ▼
  Extract (rate-limit aware client)
      │
      ▼
  Raw landing zone   data/raw/**/*.json
      │
      ▼
  Transform / Load   SQLite warehouse
      │
      ▼
  Bot decisions + SQL reports
```

### Learning outcomes

| Piece | Skill |
|-------|--------|
| `client.py` | Auth headers, pagination, 429 backoff |
| `data/raw/` | Immutable landing zone (prod analog: S3) |
| `schema.sql` | Dims vs facts, snapshots, idempotent upserts |
| `ingest/` | ETL runs table, extract → load |
| `bot/loop.py` | State machine that *generates* interesting data |

## Setup

```bash
cd spacetraders-learn
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

### Get an agent token

1. Create an account at [my.spacetraders.io](https://my.spacetraders.io)
2. Put your **account** token in `.env` as `SPACETRADERS_ACCOUNT_TOKEN`
3. Register an agent:

```bash
stlearn register --symbol LEARNER --faction COSMIC
```

That writes `SPACETRADERS_TOKEN` into `.env`.

> Weekly resets wipe agents. Re-register after a reset.

## Commands

```bash
# Public status (no token)
stlearn status

# Step 1 — public catalog ETL (no token)
stlearn ingest-catalog --pages 3

# Step 2 — private agent/ships/contracts/markets ETL
stlearn ingest

# Step 3 — play: accept contract → mine → sell → deliver (also snapshots warehouse)
stlearn play --cycles 1

# Inspect warehouse
stlearn report
stlearn query "SELECT trade_symbol, sell_price, observed_at FROM fact_market_price ORDER BY id DESC LIMIT 20"
```

## Suggested learning path

1. Run `ingest-catalog` and open a file under `data/raw/systems/`. Notice nested JSON.
2. Open `data/warehouse/spacetraders.db` (or use `stlearn query`) and compare dims vs raw.
3. Add your token, run `ingest`, watch `fact_ship_snapshot` / `fact_agent_snapshot` grow.
4. Run `play` once; re-`report` and see credits / cargo change over snapshots.
5. Improve the bot using warehouse queries (best sell prices, closer asteroids).

## Winning (later)

Early game heuristic baked into `bot/loop.py`:

1. Accept starter contract
2. Mine nearby asteroid / metal deposits
3. Sell overflow at HQ marketplace
4. Deliver contract goods and fulfill

Next upgrades (data-driven):

- Persist market ticks on a schedule → find buy-low / sell-high routes
- Track extraction yields by waypoint
- Expand fleet when credit velocity justifies ship purchase

## Note on this reset

SpaceTraders runs frequent alpha resets. Treat each reset as a fresh ingestion epoch — good practice for backfills and schema migrations.
