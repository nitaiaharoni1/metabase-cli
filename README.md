# metabase-cli

CLI for Metabase: start containers, add databases, configure dashboards from YAML, export to JSON or YAML.

## Install

**Homebrew (recommended):**

```bash
brew tap nitaiaharoni1/tools
brew install metabase-cli
```

**From source:**

```bash
cd metabase-cli
uv venv
uv pip install -e .
```

Projects (handi, tesse, opensketch) use `metabase-cli` from brew. No local path or custom scripts.

## Commands

### start

Start Metabase containers. Ensures Docker is running, runs compose up.

```bash
metabase-cli start --compose "docker compose up -d --wait postgres metabase" --port 30001
metabase-cli start -c "docker compose -f docker-compose.metabase.yml up -d --wait" -p 30003
```

### database add

Add database to Metabase from YAML config. Use `password: ${SUPABASE_DB_PASSWORD}` for env expansion.

```bash
metabase-cli database add -f metabase-dashboards/database.yaml --url http://localhost:30003
```

### database sync

Sync schema for an existing database (picks up new views/tables).

```bash
metabase-cli database sync -n "OpenSketch Analytics" --url http://localhost:30003
```

### configure

Apply YAML config to Metabase (create/update cards and dashboards).

```bash
metabase-cli configure -f metabase-dashboards/tesse.yaml --url http://localhost:30002
```

Config format: `collection`, `database_id` or `database` (name), `cards` (name, sql, display), `dashboards` (card_indices or cards with layout).

### cleanup-duplicates

Archive duplicate collections, keeping the one with most items.

```bash
metabase-cli cleanup-duplicates --collection Tesse --url http://localhost:30002
```

### export

Export dashboards and cards to JSON or YAML config.

```bash
# JSON backup
metabase-cli export -o metabase-export --url http://localhost:30001

# YAML config (dashboards as code)
metabase-cli export --to-code -o metabase-dashboards/opensketch.yaml \
  -d "OpenSketch - Overview,OpenSketch - Tool Usage,OpenSketch - File Import & Export,OpenSketch - AI Usage" \
  --url http://localhost:30003
```

## Credentials

Load order (project overrides global):

- `~/.metabase.env` (global)
- `.env.metabase` (project)
- `.env` (project)

Required: `METABASE_EMAIL`, `METABASE_PASSWORD`  
Optional: `METABASE_URL` (default: http://localhost:3000)

For `database add` with Supabase: `SUPABASE_DB_PASSWORD` (in config as `${SUPABASE_DB_PASSWORD}`).

## Project integration

Run from project root so `.env.metabase` is found. Or pass `--repo .` explicitly.

**Aligned scripts** (opensketch, tesse, handi):

| Script | opensketch | tesse | handi |
|--------|------------|-------|-------|
| `metabase` | start (port 30003) | start (port 30002) | start (port 30001) |
| `metabase:stop` | stop | stop | stop |
| `metabase:apply` | db add + configure | configure | configure |
| `metabase:sync-schema` | schema sync (Supabase) | — | — |
| `metabase:cleanup-samples` | — | — | one-time (archive sample, dedupe) |

**OpenSketch** (Supabase; apply = db add + configure):

```json
{
  "metabase": "metabase-cli start -c 'docker compose -f docker-compose.metabase.yml up -d --wait' -p 30003",
  "metabase:stop": "docker compose -f docker-compose.metabase.yml stop metabase",
  "metabase:apply": "metabase-cli database add -f metabase-dashboards/database.yaml -u http://localhost:30003 && metabase-cli configure -f metabase-dashboards/opensketch.yaml -u http://localhost:30003",
  "metabase:sync-schema": "metabase-cli database sync -n 'OpenSketch Analytics' -u http://localhost:30003"
}
```

**Tesse** (H2 file; apply = configure only; query tesse_e2e via Admin > Databases):

```json
{
  "metabase": "metabase-cli start -c 'docker compose up -d --wait metabase' -p 30002",
  "metabase:stop": "docker compose stop metabase",
  "metabase:apply": "metabase-cli configure -f metabase-dashboards/tesse.yaml -u http://localhost:30002"
}
```

**handi** (own Postgres; apply = configure; cleanup-samples = one-time):

```json
{
  "metabase": "metabase-cli start -c 'docker compose up -d --wait postgres metabase' -p 30001",
  "metabase:stop": "docker compose stop metabase",
  "metabase:apply": "metabase-cli configure -f metabase-dashboards/handi.yaml -u http://localhost:30001",
  "metabase:cleanup-samples": "metabase-cli setup-handi -u http://localhost:30001 -r ."
}
```
