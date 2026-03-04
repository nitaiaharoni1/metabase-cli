#!/usr/bin/env python3
"""Metabase CLI - start containers, export dashboards to JSON."""

import os
import subprocess
import sys
from pathlib import Path

import typer

from metabase_cli.env import load_env

app = typer.Typer(
    help="CLI for Metabase: start containers, add databases, configure dashboards from YAML, export to JSON/YAML",
    name="metabase-cli",
)


@app.command()
def start(
    compose_cmd: str = typer.Option(
        ...,
        "--compose",
        "-c",
        help="Docker compose command (e.g. 'docker compose up -d --wait postgres metabase')",
    ),
    port: int = typer.Option(3000, "--port", "-p", help="Metabase port for UI"),
    repo_root: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        path_type=Path,
        help="Path to project repo (default: cwd)",
    ),
) -> None:
    """Start Metabase containers. Ensures Docker is running, runs compose up."""
    root = repo_root or Path.cwd()
    load_env(root)

    # Check Docker
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Docker is not running. Opening Docker Desktop...", file=sys.stderr)
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Docker"], check=False)
        else:
            print("Please start Docker manually, then run this command again.", file=sys.stderr)
            raise SystemExit(1)

        # Wait for Docker
        import time

        for i in range(60):
            try:
                subprocess.run(["docker", "info"], capture_output=True, check=True)
                break
            except subprocess.CalledProcessError:
                time.sleep(2)
                print(f"Waiting for Docker... ({i + 1}/60)")
        else:
            print("Docker did not become ready in time.", file=sys.stderr)
            raise SystemExit(1)

    # Run compose
    subprocess.run(compose_cmd, shell=True, cwd=root, check=True)
    print(f"\nMetabase at http://localhost:{port}")
    print("First run: complete setup wizard, then run 'metabase-cli export' or project metabase:apply")


@app.command()
def configure(
    config: Path = typer.Option(
        ...,
        "--config",
        "-f",
        path_type=Path,
        help="Path to YAML config (e.g. metabase-dashboards/tesse.yaml)",
    ),
    no_skip_existing: bool = typer.Option(
        False,
        "--no-skip-existing",
        help="Recreate cards even if they exist (may create duplicates)",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Metabase URL (default: METABASE_URL env or http://localhost:3000)",
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        path_type=Path,
        help="Path to project repo (default: cwd)",
    ),
) -> None:
    """Apply YAML config to Metabase (create/update cards and dashboards)."""
    root = repo_root or Path.cwd()
    load_env(root)

    base_url = url or os.environ.get("METABASE_URL", "http://localhost:3000")
    email = os.environ.get("METABASE_EMAIL")
    password = os.environ.get("METABASE_PASSWORD")

    if not email or not password:
        print(
            "Error: Set METABASE_EMAIL and METABASE_PASSWORD (e.g. in .env.metabase or ~/.metabase.env)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    config_path = config if config.is_absolute() else root / config
    if not config_path.exists():
        print(f"Error: config not found: {config_path}", file=sys.stderr)
        raise SystemExit(1)

    from metabase_cli.configure import run_configure

    run_configure(
        base_url=base_url,
        email=email,
        password=password,
        config_path=config_path,
        skip_existing=not no_skip_existing,
    )


@app.command(name="cleanup-duplicates")
def cleanup_duplicates(
    collection: str = typer.Option(
        "Tesse",
        "--collection",
        "-c",
        help="Collection name to deduplicate",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Metabase URL (default: METABASE_URL env or http://localhost:3000)",
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        path_type=Path,
        help="Path to project repo (default: cwd)",
    ),
) -> None:
    """Archive duplicate collections, keeping the one with most items."""
    root = repo_root or Path.cwd()
    load_env(root)

    base_url = url or os.environ.get("METABASE_URL", "http://localhost:3000")
    email = os.environ.get("METABASE_EMAIL")
    password = os.environ.get("METABASE_PASSWORD")

    if not email or not password:
        print(
            "Error: Set METABASE_EMAIL and METABASE_PASSWORD (e.g. in .env.metabase or ~/.metabase.env)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    from metabase_cli.cleanup import run_cleanup

    run_cleanup(
        base_url=base_url,
        email=email,
        password=password,
        collection_name=collection,
    )


database_app = typer.Typer(help="Database management")

@database_app.command("add")
def database_add(
    config: Path = typer.Option(
        ...,
        "--config",
        "-f",
        path_type=Path,
        help="Path to database YAML config",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Metabase URL (default: METABASE_URL env or http://localhost:3000)",
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        path_type=Path,
        help="Path to project repo (default: cwd)",
    ),
) -> None:
    """Add database to Metabase from YAML config. Use password: ${SUPABASE_DB_PASSWORD} for env expansion."""
    root = repo_root or Path.cwd()
    load_env(root)

    base_url = url or os.environ.get("METABASE_URL", "http://localhost:3000")
    email = os.environ.get("METABASE_EMAIL")
    password = os.environ.get("METABASE_PASSWORD")

    if not email or not password:
        print(
            "Error: Set METABASE_EMAIL and METABASE_PASSWORD (e.g. in .env.metabase or ~/.metabase.env)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    config_path = config if config.is_absolute() else root / config
    if not config_path.exists():
        print(f"Error: config not found: {config_path}", file=sys.stderr)
        raise SystemExit(1)

    from metabase_cli.database import run_database_add

    run_database_add(
        base_url=base_url,
        email=email,
        password=password,
        config_path=config_path,
    )


@database_app.command("sync")
def database_sync(
    name: str = typer.Option(
        ...,
        "--name",
        "-n",
        help="Database name to sync (e.g. OpenSketch Analytics)",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Metabase URL (default: METABASE_URL env or http://localhost:3000)",
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        path_type=Path,
        help="Path to project repo (default: cwd)",
    ),
) -> None:
    """Sync schema for an existing database (picks up new views/tables)."""
    root = repo_root or Path.cwd()
    load_env(root)

    base_url = url or os.environ.get("METABASE_URL", "http://localhost:3000")
    email = os.environ.get("METABASE_EMAIL")
    password = os.environ.get("METABASE_PASSWORD")

    if not email or not password:
        print(
            "Error: Set METABASE_EMAIL and METABASE_PASSWORD (e.g. in .env.metabase or ~/.metabase.env)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    from metabase_cli.database import run_database_sync

    run_database_sync(
        base_url=base_url,
        email=email,
        password=password,
        database_name=name,
    )


app.add_typer(database_app, name="database")


@app.command(name="dashboards")
def list_dashboards(
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Metabase URL (default: METABASE_URL env or http://localhost:3000)",
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        path_type=Path,
        help="Path to project repo (default: cwd)",
    ),
) -> None:
    """List all dashboards."""
    root = repo_root or Path.cwd()
    load_env(root)

    base_url = url or os.environ.get("METABASE_URL", "http://localhost:3000")
    email = os.environ.get("METABASE_EMAIL")
    password = os.environ.get("METABASE_PASSWORD")

    if not email or not password:
        print(
            "Error: Set METABASE_EMAIL and METABASE_PASSWORD (e.g. in .env.metabase or ~/.metabase.env)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    from metabase_cli.api import login, req

    try:
        token = login(base_url, email, password)
    except Exception as e:
        print(f"Login failed: {e}", file=sys.stderr)
        raise SystemExit(1)

    dash_resp = req(base_url, token, "GET", "/api/dashboard")
    dash_list = dash_resp if isinstance(dash_resp, list) else dash_resp.get("data", [])
    dash_list = [d for d in dash_list if isinstance(d, dict) and "name" in d and "id" in d]

    for d in sorted(dash_list, key=lambda x: x["name"]):
        print(f"  {d['id']}: {d['name']}")


@app.command()
def export(
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        path_type=Path,
        help="Output directory (JSON) or file path (--to-code)",
    ),
    to_code: bool = typer.Option(
        False,
        "--to-code/--no-to-code",
        help="Export to YAML config (dashboards as code) instead of JSON",
    ),
    dashboards: str | None = typer.Option(
        None,
        "--dashboards",
        "-d",
        help="Comma-separated dashboard names to export (--to-code only; default: all)",
    ),
    database_name: str = typer.Option(
        "OpenSketch Analytics",
        "--database",
        help="Database name in config (--to-code only)",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Metabase URL (default: METABASE_URL env or http://localhost:3000)",
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo",
        "-r",
        path_type=Path,
        help="Path to project repo (default: cwd)",
    ),
) -> None:
    """Export dashboards and cards to JSON or YAML config via Metabase API."""
    root = repo_root or Path.cwd()
    load_env(root)

    base_url = url or os.environ.get("METABASE_URL", "http://localhost:3000")
    email = os.environ.get("METABASE_EMAIL")
    password = os.environ.get("METABASE_PASSWORD")

    if not email or not password:
        print(
            "Error: Set METABASE_EMAIL and METABASE_PASSWORD (e.g. in .env.metabase or ~/.metabase.env)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if to_code:
        from metabase_cli.export import run_export_to_code

        out_path = output if output.is_absolute() else root / output
        dashboard_names = [s.strip() for s in dashboards.split(",")] if dashboards else None
        run_export_to_code(
            base_url=base_url,
            email=email,
            password=password,
            output=out_path,
            dashboard_names=dashboard_names,
            database_name=database_name,
        )
    else:
        from metabase_cli.export import run_export

        run_export(base_url=base_url, email=email, password=password, output=output)


if __name__ == "__main__":
    app()
