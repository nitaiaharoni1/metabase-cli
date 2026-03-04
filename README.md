# metabase-cli

CLI for Metabase: start containers, export dashboards to JSON.

## Install

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
