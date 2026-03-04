"""Add cards to an existing dashboard via YAML config."""
import sys
import urllib.error
from pathlib import Path

from metabase_cli.api import login, req

STRIP_KEYS = [
    "collection",
    "last-edit-info",
    "creator_id",
    "last_viewed_at",
    "updated_at",
    "created_at",
    "embedding_params",
    "moderation_reviews",
    "made_public_by_id",
    "entity_id",
    "public_uuid",
    "dependency_analysis_version",
    "is_remote_synced",
    "archived_directly",
    "can_restore",
    "can_write",
    "can_delete",
]


def _resolve_db_id(token: str, base_url: str, config: dict) -> int:
    db_id = config.get("database_id")
    if db_id is not None:
        return int(db_id)
    db_name = config.get("database")
    if not db_name:
        print("Error: config must have 'database_id' or 'database'", file=sys.stderr)
        raise SystemExit(1)
    dbs = req(base_url, token, "GET", "/api/database")
    db_list = dbs.get("data", dbs) if isinstance(dbs, dict) else dbs
    for d in db_list or []:
        if isinstance(d, dict) and d.get("name") == db_name:
            return d["id"]
    print(f"Error: database '{db_name}' not found in Metabase", file=sys.stderr)
    raise SystemExit(1)


def _find_collection_id(token: str, base_url: str, name: str) -> int | None:
    for endpoint in ["/api/collection/tree", "/api/collection"]:
        try:
            data = req(base_url, token, "GET", endpoint)
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            found = _search_collection(data if isinstance(data, list) else [data], name)
            if found is not None:
                return found
        except Exception:
            continue
    return None


def _search_collection(items: list, name: str) -> int | None:
    for item in items or []:
        if isinstance(item, dict) and item.get("name") == name:
            cid = item.get("id")
            if cid is not None:
                return cid
        for key in ("children", "children__", "subcollections"):
            found = _search_collection(item.get(key) or [], name)
            if found is not None:
                return found
    return None


def run_add_cards(
    *,
    base_url: str,
    email: str,
    password: str,
    config_path: Path,
) -> None:
    """Create cards from YAML and add them to an existing dashboard."""
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
        raise SystemExit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if not config:
        print("Error: empty config", file=sys.stderr)
        raise SystemExit(1)

    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    db_id = _resolve_db_id(token, base_url, config)
    collection_name = config.get("collection")
    coll_id = None
    if collection_name:
        coll_id = _find_collection_id(token, base_url, collection_name)

    # Build card_by_name from config
    cards_resp = req(base_url, token, "GET", "/api/card")
    all_cards = cards_resp if isinstance(cards_resp, list) else cards_resp.get("data", [])
    existing_cards = {c["name"]: c for c in all_cards if isinstance(c, dict) and "name" in c and not c.get("archived")}

    card_by_name: dict[str, int] = {}
    for c in config.get("cards", []):
        name = c["name"]
        sql = (c.get("sql") or c.get("query") or "").strip()
        display = c.get("display") or c.get("viz") or "table"
        viz_settings = c.get("visualization_settings", {})

        if not sql:
            continue

        payload: dict = {
            "name": name,
            "display": display,
            "visualization_settings": viz_settings,
            "dataset_query": {
                "type": "native",
                "native": {"query": sql, "template-tags": {}},
                "database": db_id,
            },
        }
        if coll_id:
            payload["collection_id"] = coll_id

        if name in existing_cards:
            card_by_name[name] = existing_cards[name]["id"]
            print(f"Using existing card: {name}")
        else:
            card = req(base_url, token, "POST", "/api/card", payload)
            card_by_name[name] = card["id"]
            print(f"Created card: {name}")

    if not card_by_name:
        print("No cards to add.")
        return

    dashboard_name = config.get("dashboard")
    if not dashboard_name:
        print("Error: config must have 'dashboard' (target dashboard name)", file=sys.stderr)
        raise SystemExit(1)

    dash_resp = req(base_url, token, "GET", "/api/dashboard")
    dash_list = dash_resp if isinstance(dash_resp, list) else dash_resp.get("data", [])
    dash_list = [d for d in dash_list if isinstance(d, dict) and d.get("name") and d.get("id") and not d.get("archived")]
    target = next((d for d in dash_list if d["name"] == dashboard_name), None)
    if not target:
        print(f"Error: dashboard '{dashboard_name}' not found", file=sys.stderr)
        raise SystemExit(1)

    full = req(base_url, token, "GET", f"/api/dashboard/{target['id']}")
    existing_dashcards = full.get("dashcards") or []
    max_row = max((d.get("row", 0) + d.get("size_y", 4) for d in existing_dashcards if isinstance(d, dict)), default=0)

    # Build new dashcards
    card_names = list(card_by_name.keys())
    for i, cname in enumerate(card_names):
        existing_dashcards.append({
            "id": -(i + 1),
            "card_id": card_by_name[cname],
            "row": max_row + (i // 2) * 4,
            "col": (i % 2) * 6,
            "size_x": 6,
            "size_y": 4,
            "series": [],
            "visualization_settings": {},
            "parameter_mappings": [],
            "dashboard_tab_id": None,
            "action_id": None,
        })

    cards_payload = [
        {
            "id": d.get("id"),
            "card_id": d.get("card_id"),
            "row": d.get("row", 0),
            "col": d.get("col", 0),
            "size_x": d.get("size_x", 6),
            "size_y": d.get("size_y", 4),
            "series": d.get("series", []),
            "visualization_settings": d.get("visualization_settings", {}),
            "parameter_mappings": d.get("parameter_mappings", []),
            "dashboard_tab_id": d.get("dashboard_tab_id"),
            "action_id": d.get("action_id"),
        }
        for d in existing_dashcards
        if isinstance(d, dict) and d.get("card_id")
    ]

    for k in STRIP_KEYS:
        full.pop(k, None)
    full["cards"] = cards_payload
    full.pop("dashcards", None)
    req(base_url, token, "PUT", f"/api/dashboard/{target['id']}", full)
    print(f"Added {len(card_names)} card(s) to {dashboard_name}")

    print(f"\nDone! Open {base_url}")
