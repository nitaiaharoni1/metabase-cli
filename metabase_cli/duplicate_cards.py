"""Archive duplicate cards, keeping one per name and updating dashboards to use it."""
import sys
import urllib.error
from collections import defaultdict

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


def run_cleanup_duplicate_cards(
    *,
    base_url: str,
    email: str,
    password: str,
    collection: str | None = None,
    dry_run: bool = False,
) -> None:
    """Find cards with duplicate names, keep one, update dashboards to use it, archive rest."""
    try:
        token = login(base_url, email, password)
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

    # Fetch all cards
    cards_resp = req(base_url, token, "GET", "/api/card")
    card_list = cards_resp if isinstance(cards_resp, list) else cards_resp.get("data", [])
    cards = [c for c in (card_list or []) if isinstance(c, dict) and not c.get("archived")]

    # Group by name
    by_name: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        name = c.get("name")
        if name:
            by_name[name].append(c)

    duplicates = {k: sorted(v, key=lambda x: x["id"]) for k, v in by_name.items() if len(v) > 1}
    if not duplicates:
        print("No duplicate card names found.")
        return

    if collection:
        coll_resp = req(base_url, token, "GET", "/api/collection/tree")
        coll_data = coll_resp if isinstance(coll_resp, list) else coll_resp.get("data", [])
        coll_id = _find_collection_id(coll_data, collection)
        if coll_id is None:
            print(f"Collection '{collection}' not found", file=sys.stderr)
            raise SystemExit(1)
        # Filter to cards in this collection
        in_coll = set()
        try:
            items = req(base_url, token, "GET", f"/api/collection/{coll_id}/items")
            for item in items or []:
                if isinstance(item, dict) and item.get("model") == "card":
                    in_coll.add(item.get("id") or item.get("model_id"))
        except Exception:
            pass
        duplicates = {
            k: [c for c in v if c["id"] in in_coll]
            for k, v in duplicates.items()
            if any(c["id"] in in_coll for c in v)
        }
        # Re-filter to only names that still have >1
        duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}

    if not duplicates:
        print("No duplicate card names found in collection.")
        return

    # Fetch all dashboards with their dashcards
    dash_resp = req(base_url, token, "GET", "/api/dashboard")
    dash_list = dash_resp if isinstance(dash_resp, list) else dash_resp.get("data", [])
    dash_list = [d for d in dash_list if isinstance(d, dict) and d.get("id") and not d.get("archived")]

    dashboards_full: dict[int, dict] = {}
    for d in dash_list:
        try:
            full = req(base_url, token, "GET", f"/api/dashboard/{d['id']}")
            if isinstance(full, dict) and "dashcards" in full:
                dashboards_full[full["id"]] = full
        except Exception:
            pass

    # Build map: card_id -> [(dashboard_id, dashcard)]
    card_to_dashcards: dict[int, list[tuple[int, dict]]] = defaultdict(list)
    for dash_id, full in dashboards_full.items():
        for dc in full.get("dashcards") or []:
            if isinstance(dc, dict) and dc.get("card_id"):
                card_to_dashcards[dc["card_id"]].append((dash_id, dc))

    archived = 0
    for name, card_list_sorted in sorted(duplicates.items()):
        keep = card_list_sorted[0]
        keep_id = keep["id"]
        to_archive = card_list_sorted[1:]

        for dup in to_archive:
            dup_id = dup["id"]
            refs = card_to_dashcards.get(dup_id, [])
            if dry_run:
                print(f"[dry-run] Would keep {name} id={keep_id}, archive id={dup_id} (used in {len(refs)} dashcards)")
                archived += 1
                continue

            # Update dashboards that use dup_id to use keep_id instead
            for dash_id, dc in refs:
                full = dashboards_full.get(dash_id)
                if not full:
                    continue
                raw_dashcards = full.get("dashcards") or []
                updated = False
                for i, d in enumerate(raw_dashcards):
                    if isinstance(d, dict) and d.get("card_id") == dup_id:
                        raw_dashcards[i] = {**d, "card_id": keep_id}
                        updated = True
                if updated:
                    # Build clean dashcards for PUT (strip nested card, keep required fields)
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
                        for d in raw_dashcards
                        if isinstance(d, dict) and d.get("card_id")
                    ]
                    for k in STRIP_KEYS:
                        full.pop(k, None)
                    full["cards"] = cards_payload
                    full.pop("dashcards", None)
                    try:
                        req(base_url, token, "PUT", f"/api/dashboard/{dash_id}", full)
                        print(f"  Updated dashboard {dash_id}: {name} now uses card id={keep_id}")
                    except urllib.error.HTTPError as e:
                        print(f"  Failed to update dashboard {dash_id}: {e.code}", file=sys.stderr)

            # Archive the duplicate card
            try:
                full_card = req(base_url, token, "GET", f"/api/card/{dup_id}")
                if isinstance(full_card, dict):
                    full_card["archived"] = True
                    req(base_url, token, "PUT", f"/api/card/{dup_id}", full_card)
                    print(f"Archived duplicate: {name} (id={dup_id})")
                    archived += 1
            except urllib.error.HTTPError as e:
                print(f"Failed to archive card {dup_id}: {e.code}", file=sys.stderr)

    print(f"\nDone. Archived {archived} duplicate card(s).")


def _find_collection_id(items: list, name: str) -> int | None:
    for item in items or []:
        if isinstance(item, dict):
            if item.get("name") == name:
                cid = item.get("id")
                if cid is not None:
                    return cid
            for key in ("children", "children__", "subcollections"):
                found = _find_collection_id(item.get(key) or [], name)
                if found is not None:
                    return found
    return None
