# metabase-cli

CLI for Metabase: start containers, export dashboards to JSON.

## Install

**Homebrew** (recommended):

```bash
brew tap nitaiaharoni1/tools
brew install metabase-cli
```

**From source** (for development):

```bash
cd metabase-cli
uv venv
uv pip install -e .
```

Projects (handi, tesse, opensketch) invoke via `../metabase-cli/bin/metabase-cli` when cloned as siblings under REPOS.

## Commands

### start

Start Metabase containers. Ensures Docker is running, runs compose up.

```bash
metabase-cli start --compose "docker compose up -d --wait postgres metabase" --port 30001
metabase-cli start -c "docker compose -f docker-compose.metabase.yml up -d --wait" -p 30003
```

### export

Export dashboards and cards to JSON via Metabase API.

```bash
metabase-cli export --output metabase-dashboards
metabase-cli export -o metabase-dashboards --url http://localhost:30001
```

### configure

Apply YAML config to Metabase (create/update cards and dashboards).

```bash
metabase-cli configure -f metabase-dashboards/tesse.yaml --url http://localhost:30002
```

### cleanup-duplicates

Archive duplicate collections, keeping the one with most items.

```bash
metabase-cli cleanup-duplicates --collection Tesse
```

## Credentials

Load order (project overrides global):

- `~/.metabase.env` (global)
- `.env.metabase` (project)
- `.env` (project)

Required: `METABASE_EMAIL`, `METABASE_PASSWORD`  
Optional: `METABASE_URL` (default: http://localhost:3000)

## Project integration

In handi, tesse, opensketch `package.json`:

```json
{
  "metabase": "metabase-cli start -c 'docker compose up -d --wait postgres metabase' -p 30001",
  "metabase:export": "metabase-cli export -o metabase-dashboards --url http://localhost:30001"
}
```

Run from project root so `.env.metabase` is found. Or pass `--repo .` explicitly.
