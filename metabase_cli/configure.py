"""Apply Metabase dashboard config from YAML via API."""
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


def _find_collection_id(token: str, base_url: str, name: str) -> int | None:
    """Search collection tree for name match."""
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
    items = items or []
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            cid = item.get("id")
            if cid is not None:
                return cid
        for key in ("children", "children__", "subcollections"):
            found = _search_collection(item.get(key) or [], name)
            if found is not None:
                return found
    return None


def _resolve_db_id(token: str, base_url: str, config: dict) -> int:
    """Resolve database ID from config (database_id or database name)."""
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


def run_configure(
    *,
    base_url: str,
    email: str,
    password: str,
    config_path: Path,
    skip_existing: bool = True,
) -> None:
    """Apply YAML config to Metabase."""
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
        if not coll_id:
            try:
                coll = req(base_url, token, "POST", "/api/collection", {"name": collection_name, "color": "#509EE3"})
                coll_id = coll.get("id")
                print(f"Created collection: {collection_name}")
            except Exception as e:
                print(f"Failed to create collection: {e}", file=sys.stderr)

    # Fetch existing cards in collection
    existing_names: set[str] = set()
    existing_card_ids: dict[str, int] = {}
    if skip_existing and coll_id:
        try:
            items = req(base_url, token, "GET", f"/api/collection/{coll_id}/items")
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and item.get("model") == "card":
                    name = item.get("name", "")
                    existing_names.add(name)
                    existing_card_ids[name] = item.get("id") or item.get("model_id")
        except Exception:
            pass

    # Fetch all existing cards for update path (opensketch-style)
    cards_resp = req(base_url, token, "GET", "/api/card")
    all_cards = cards_resp if isinstance(cards_resp, list) else cards_resp.get("data", [])
    existing_cards = {c["name"]: c for c in all_cards if isinstance(c, dict) and "name" in c}
    dash_resp = req(base_url, token, "GET", "/api/dashboard")
    dash_list = dash_resp if isinstance(dash_resp, list) else dash_resp.get("data", [])
    existing_dashboards = {d["name"]: d for d in dash_list if isinstance(d, dict) and "name" in d and "id" in d}

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

        if skip_existing and name in existing_names and name in existing_card_ids:
            card_by_name[name] = existing_card_ids[name]
            print(f"Skipped (exists): {name}")
            continue

        if name in existing_cards:
            full = req(base_url, token, "GET", f"/api/card/{existing_cards[name]['id']}")
            for k in STRIP_KEYS:
                full.pop(k, None)
            full.update(payload)
            req(base_url, token, "PUT", f"/api/card/{existing_cards[name]['id']}", full)
            card_by_name[name] = existing_cards[name]["id"]
            print(f"Updated card: {name}")
        else:
            card = req(base_url, token, "POST", "/api/card", payload)
            card_by_name[name] = card["id"]
            print(f"Created card: {name}")

    # Build dashboards
    card_order = list(card_by_name.keys())
    for d in config.get("dashboards", []):
        dash_name = d["name"]
        dashcards = []

        # Support card_indices (tesse style) or cards (opensketch style)
        card_indices = d.get("card_indices")
        if card_indices is not None:
            for i, idx in enumerate(card_indices):
                if 0 <= idx < len(card_order):
                    cname = card_order[idx]
                    if cname in card_by_name:
                        dashcards.append({
                            "id": -(i + 1),
                            "card_id": card_by_name[cname],
                            "row": (i // 2) * 4,
                            "col": (i % 2) * 6,
                            "size_x": 6,
                            "size_y": 4,
                            "series": [],
                            "visualization_settings": {},
                            "parameter_mappings": [],
                            "dashboard_tab_id": None,
                            "action_id": None,
                        })
        else:
            for i, item in enumerate(d.get("cards", [])):
                cname = item.get("card")
                if cname not in card_by_name:
                    print(f"  Warning: card '{cname}' not found, skipping")
                    continue
                dashcards.append({
                    "id": -(i + 1),
                    "card_id": card_by_name[cname],
                    "row": item.get("row", 0),
                    "col": item.get("col", 0),
                    "size_x": item.get("size_x", 6),
                    "size_y": item.get("size_y", 4),
                    "series": [],
                    "visualization_settings": {},
                    "parameter_mappings": [],
                    "dashboard_tab_id": None,
                    "action_id": None,
                })

        if not dashcards:
            continue

        if dash_name in existing_dashboards:
            dash_id = existing_dashboards[dash_name]["id"]
            full = req(base_url, token, "GET", f"/api/dashboard/{dash_id}")
            for k in STRIP_KEYS:
                full.pop(k, None)
            full["cards"] = dashcards
            full.pop("dashcards", None)
            if coll_id:
                full["collection_id"] = coll_id
            req(base_url, token, "PUT", f"/api/dashboard/{dash_id}", full)
            print(f"Updated dashboard: {dash_name} ({len(dashcards)} cards)")
        else:
            dash = req(base_url, token, "POST", "/api/dashboard", {"name": dash_name, "collection_id": coll_id})
            dash_id = dash["id"]
            full = req(base_url, token, "GET", f"/api/dashboard/{dash_id}")
            for k in STRIP_KEYS:
                full.pop(k, None)
            full["cards"] = dashcards
            full.pop("dashcards", None)
            req(base_url, token, "PUT", f"/api/dashboard/{dash_id}", full)
            print(f"Created dashboard: {dash_name} ({len(dashcards)} cards)")

    print(f"\nDone! Open {base_url}")
