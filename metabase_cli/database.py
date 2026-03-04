"""Add database to Metabase via API."""
import os
import re
import sys
import urllib.error
from pathlib import Path

from metabase_cli.api import login, req


def _expand_env(val: str) -> str:
    """Expand ${VAR} in string from environment."""
    if not isinstance(val, str):
        return val

    def repl(m: re.Match) -> str:
        return os.environ.get(m.group(1), m.group(0))

    return re.sub(r"\$\{([^}]+)\}", repl, val)


def _load_config(config_path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
        raise SystemExit(1)

    with open(config_path) as f:
        raw = yaml.safe_load(f)
    if not raw:
        print("Error: empty config", file=sys.stderr)
        raise SystemExit(1)

    # Expand env vars in string values
    def expand(obj):
        if isinstance(obj, dict):
            return {k: expand(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [expand(v) for v in obj]
        if isinstance(obj, str):
            return _expand_env(obj)
        return obj

    return expand(raw)


def run_database_add(
    *,
    base_url: str,
    email: str,
    password: str,
    config_path: Path,
) -> None:
    """Add database to Metabase from YAML config."""
    config = _load_config(config_path)
    name = config.get("name")
    if not name:
        print("Error: config must have 'name'", file=sys.stderr)
        raise SystemExit(1)

    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    # Check if database already exists
    dbs = req(base_url, token, "GET", "/api/database")
    db_list = dbs.get("data", dbs) if isinstance(dbs, dict) else dbs
    for d in db_list or []:
        if isinstance(d, dict) and d.get("name") == name:
            print(f"Database '{name}' already exists.")
            return

    engine = config.get("engine", "postgres")
    details = config.get("details", {})
    if not details:
        # Flatten top-level connection keys into details
        details = {
            k: config[k]
            for k in ("host", "port", "dbname", "user", "password", "ssl", "ssl-mode")
            if k in config
        }

    payload = {
        "name": name,
        "engine": engine,
        "details": details,
    }

    try:
        result = req(base_url, token, "POST", "/api/database", payload)
        db_id = result.get("id")
        if db_id:
            print(f"Added database: {name} (id={db_id})")
            # Trigger schema sync
            try:
                req(base_url, token, "POST", f"/api/database/{db_id}/sync_schema", {})
                print("Schema sync triggered.")
            except Exception:
                pass
            print(f"Open Metabase at {base_url}")
        else:
            print(f"Unexpected response: {result}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        print(f"Failed to add database: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)


def run_database_sync(
    *,
    base_url: str,
    email: str,
    password: str,
    database_name: str,
) -> None:
    """Sync schema for an existing database."""
    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    dbs = req(base_url, token, "GET", "/api/database")
    db_list = dbs.get("data", dbs) if isinstance(dbs, dict) else dbs
    db_id = None
    for d in db_list or []:
        if isinstance(d, dict) and d.get("name") == database_name:
            db_id = d["id"]
            break
    if not db_id:
        print(f"Database '{database_name}' not found.", file=sys.stderr)
        raise SystemExit(1)

    req(base_url, token, "POST", f"/api/database/{db_id}/sync_schema", {})
    print(f"Schema sync triggered for {database_name}.")
