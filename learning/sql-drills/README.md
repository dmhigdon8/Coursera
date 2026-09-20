# SQL drills

Interview-style / warehouse-native SQL practice against this project's Postgres + dbt marts.

Conventions:
- One file per drill: `NNN_short_slug.sql`
- Header comment: question, assumed grain, tables used
- Prefer querying `staging_marts.*` (see STATUS.md naming quirk) unless schemas are cleaned up
- Commit a working answer; optional `-- alternate:` solutions welcome

Start from [`LEARNING_PLAN.md`](../LEARNING_PLAN.md) Phase 1.
