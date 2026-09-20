# Learning Plan — Sports Data Platform

**Owner:** Daniel Higdon  
**Primary repo:** [f1-data-engineering](https://github.com/dmhigdon8/f1-data-engineering) (grow this)  
**Supporting repos:** [LeetCode](https://github.com/dmhigdon8/LeetCode), [Coursera](https://github.com/dmhigdon8/Coursera) (DSA), [Space-Traders](https://github.com/dmhigdon8/Space-Traders) (optional ingestion sandbox)

**Goal order (your tops):**
1. SQL problem-solving  
2. dbt — understand and get real mileage  
3. AI — understand and get real mileage  
4. DSA in Python  
5. Data ingestion  

Sports is the domain glue: **F1 first (already working), then MLB, then NFL**, same patterns each time.

---

## Design principle

One warehouse, many sports — not three disconnected toy projects.

```text
APIs / files
   → ingest (Python)
   → raw landing (local JSON + S3)
   → Postgres raw schemas
   → dbt staging → intermediate → marts
   → SQL drills + AI-assisted analysis on marts
```

F1 already proves the path (Jolpica → S3 → Postgres → dbt, `dbt build` 34/34). Everything below **extends that spine** instead of replacing it.

Space Traders stays optional: great for API polling / rate limits / game-state facts, but **not** the main SQL/dbt gym. Sports data has richer join/window/grain problems.

---

## How the five skills map to work

| Priority | Skill | Where you practice it | “Done looks like” |
|----------|--------|------------------------|-------------------|
| 1 | SQL | `sql/drills/`, ad-hoc on `staging_marts.*`, interview-style prompts on your own tables | You can answer grain, window, and gap questions without guessing |
| 2 | dbt | `dbt_f1/` → later `dbt_sports/` or multi-project | Incremental models, tests that catch real bugs, docs people could trust |
| 3 | AI | Workflow on this repo + small applied experiments | You use AI to accelerate, verify, and document — not to skip understanding |
| 4 | DSA | Coursera Algorithmic Toolbox + LeetCode, 3–5 problems/week | Patterns stick; you can explain Big-O and map patterns to pipeline code |
| 5 | Ingestion | `ingest/` for F1, then MLB/NFL extractors | Idempotent loads, clear raw contracts, incremental / season-partitioned pulls |

---

## Phase 0 — Lock the F1 foundation (short)

You’re basically here already. Finish the operational debt so learning isn’t blocked by machine/secrets churn.

- [ ] Rotate `f1-pipeline` AWS key; stop sharing one key across machines forever  
- [ ] Confirm Dell as primary raw-data machine (STATUS proposal)  
- [ ] Add `.gitattributes` (`* text=auto`)  
- [ ] One-command bootstrap notes kept truthful for Mac + Dell  

**Exit:** Fresh clone on Dell → extract → load → `dbt build` green without tribal knowledge.

---

## Phase 1 — SQL gym on F1 marts (highest leverage next)

Build a `sql/drills/` folder of **problems against your own warehouse**, not only generic LeetCode SQL.

### Drill themes (write the question + a reference answer)

1. **Grain checks** — “One row per driver-race?” Prove with `COUNT(*)` vs `COUNT(DISTINCT …)`.  
2. **Windows** — season points running total; rank within race; gap to leader.  
3. **Gaps / islands** — streak of podium finishes; races since last DNF.  
4. **Slowly changing truth** — constructor changes; who drove for whom when.  
5. **Anti-joins** — drivers who entered a season but have zero sprint results.  
6. **Performance reading** — `EXPLAIN ANALYZE` on a heavy drill; add an index only if earned.

### Cadence

- **3 SQL drills / week** (45–60 min), committed as `sql/drills/001_….sql` with a short header comment: question, assumed grain, answer query.  
- After each dbt model you add, write **one drill that would have failed** if the model grain were wrong.

### Stretch

- Recreate 5 classic interview problems (second highest salary style, sessionization, retention) **using race/driver tables** so muscle memory stays in-domain.

**Exit:** 12+ drills in repo; you can explain grain of `fct_race_results` cold.

---

## Phase 2 — Make dbt do real work (not just `SELECT *` staging)

Current shape: staging (`stg_drivers/races/results/sprint_results`) + marts (`dim_*`, `fct_*`). Next skills, in order:

| Step | dbt skill | Concrete F1 task |
|------|-----------|------------------|
| 2a | Sources & freshness | Declare Jolpica-loaded raw tables; freshness warn on stale seasons |
| 2b | Tests that hurt | `unique`, `not_null`, accepted ranges; **relationships** race→driver; custom singular test: points ≥ 0 |
| 2c | Intermediate models | `int_results_with_standings` (windows live here, not in marts) |
| 2d | Incremental | `fct_race_results` incremental on `season` or `race_id` after full refresh baseline |
| 2e | Macros | `finish_position_surrogate`, season filter macro — one macro used in 3+ models |
| 2f | Docs & exposures | `dbt docs generate`; exposure “Driver season dashboard” |
| 2g | Packages | `dbt_utils` (`surrogate_key`, `deduplicate`) — use deliberately, don’t carpet-import |
| 2h | CI | GitHub Action: `dbt parse` + `dbt build` against Docker Postgres on PR |

Also fix/document the schema naming quirk (`staging_marts` vs `marts`) so future-you queries the right place — or set `+schema` cleanly so marts land in `marts`.

**Exit:** Incremental path works; CI runs dbt on PR; at least one singular test has caught a bad load in practice (force a bad row once on purpose).

---

## Phase 3 — Grow into multi-sport (ingestion + dbt at once)

Same contracts every time. Do **not** invent a new architecture for baseball.

### Suggested order

1. **F1 deepen** — more Jolpica endpoints you don’t have yet (qualifying, pit stops, lap times if available / licensed). Prefer endpoints that create interesting grains.  
2. **MLB** — start narrow: schedules + game results for one season (e.g. Stats API or a stable open source).  
3. **NFL** — schedules + weekly results; avoid betting odds rabbit holes early.

### Repo layout target (evolve toward)

```text
ingest/
  f1/
  mlb/
  nfl/
raw/                    # or sport-prefixed S3 keys
sql/init/               # raw schemas: raw_f1, raw_mlb, raw_nfl
dbt_sports/             # or keep dbt_f1 and add dbt_mlb — decide in 3a
  models/staging/...
  models/marts/...
sql/drills/
```

**Decision 3a (pick once):**
- **A (recommended):** one dbt project `dbt_sports` with `f1__`, `mlb__`, `nfl__` model prefixes and shared macros  
- **B:** separate dbt projects per sport (simpler isolation, more profile/CI duplication)

### Ingestion checklist per new sport

- [ ] Postman (or httpx scratch) understands auth, pagination, rate limits  
- [ ] Extract writes **immutable raw JSON** (date-partitioned keys on S3)  
- [ ] Load is **idempotent** (you already do this for F1)  
- [ ] One dbt source + two staging models + one fact before expanding  

**Exit:** MLB (or NFL) has extract → raw → staging → one fact, plus 3 SQL drills on that fact.

---

## Phase 4 — AI: get mileage without outsourcing thinking

Treat AI as a **force multiplier with verification gates**, not as the source of truth.

### Weekly AI practice (tied to this repo)

| Use | Do this | Verification gate |
|-----|---------|-------------------|
| Draft dbt models | “Here’s source YAML + 3 raw rows; draft `stg_…`” | You rewrite grain + tests before merge |
| Explain plans | Paste `EXPLAIN ANALYZE` + ask for indexed approach | Re-run explain; keep only measured wins |
| SQL drills | Ask for *alternate* solutions (window vs group) | You can teach both approaches |
| Debugging | Paste dbt error + model + `_schema.yml` | You can state root cause in one sentence |
| Docs | Generate model descriptions | You trim hallucinations; no invented columns |

### Small applied AI projects (pick one after Phase 2)

1. **Warehouse Q&A** — RAG over `dbt docs` / schema YAML so you can ask “grain of fct_race_results?”  
2. **Narrative generator** — given a race fact row set, draft a race report; evaluate factual errors  
3. **Anomaly assistant** — flag odd pit/points outliers; you label true/false positives  

Avoid jumping into “predict the championship” ML until SQL/dbt grain is boringly solid — otherwise you’ll debug features that were wrong upstream.

**Exit:** A short `AI_WORKFLOW.md` in this repo listing prompts you reuse + gates you refuse to skip.

---

## Phase 5 — DSA in Python (parallel track, lighter weekly load)

Keep this **separate from the warehouse** so you don’t muddy “pipeline code” with contest patterns — then deliberately reconnect.

### Cadence

- **Coursera Algorithmic Toolbox** — finish modules in order (already started in Coursera repo).  
- **LeetCode** — 3 problems/week, tag by pattern (two pointers, sliding window, hash map, stack, BFS/DFS, heap, binary search).  
- **Bridge note** (5 lines in the LeetCode README): where this pattern appears in data eng (e.g. sliding window → time-series features; heap → top-k lap times; graph BFS → team influence / schedule graphs).

### Sports-flavored applied DSA (optional monthly)

- Parse a season schedule into a graph; shortest path between venues (NFL travel toy).  
- Streaming median of lap times (two heaps).  
- Compress race event sequences (run-length / stack).

**Exit:** Consistent weekly streak; you can explain 8 core patterns without looking them up.

---

## Suggested weekly rhythm (sustainable)

Assuming ~6–8 focused hours/week:

| Block | Time | Focus |
|-------|------|--------|
| Mon/Tue | 1.5h | SQL drill on warehouse |
| Wed | 1.5h | dbt feature (test, incremental, macro, or CI) |
| Thu | 1h | Ingestion ticket (one endpoint or idempotency improvement) |
| Fri | 1h | AI-assisted review of the week’s PR + update docs |
| Weekend | 1–1.5h | DSA (Coursera or LeetCode) |

Protect SQL + dbt as first-class; ingestion and AI support them; DSA stays a steady parallel.

---

## 90-day milestone sketch (no calendar promises — capability targets)

**By ~30 days of steady work**
- `sql/drills/` has ≥12 F1 problems with answers  
- dbt: intermediate model + stronger tests + docs generated  
- AWS key rotated; Dell workflow boring  

**By ~60 days**
- At least one incremental model in production path  
- CI runs `dbt build` on PRs  
- Second sport skeleton (MLB recommended): extract + raw + 1 fact  

**By ~90 days**
- Multi-sport mart you can query for “compare competitive balance” style SQL  
- AI workflow doc + one small applied experiment  
- DSA: Algorithmic Toolbox meaningfully advanced; LeetCode pattern coverage documented  

---

## What not to do (keeps this learnable)

- Don’t stand up Kafka/Spark until Postgres + dbt + SQL drills feel easy.  
- Don’t add baseball *and* NFL in the same week.  
- Don’t let Space Traders or a new repo steal the dbt muscle — optional side quest only.  
- Don’t accept AI-generated models without stating grain + writing a test.

---

## Immediate next actions (start here)

1. Create `sql/drills/001_grain_fct_race_results.sql` — prove primary key grain.  
2. Create `sql/drills/002_gap_to_leader.sql` — window functions on a single race.  
3. Add a singular dbt test that fails if duplicate driver-race rows appear.  
4. Schedule next sport only after (1–3) are merged and you’ve used them once cold.

When you’re ready to execute, say which machine you’re on (Dell/Mac) and we start with drill 001 + the singular test in this repo.
