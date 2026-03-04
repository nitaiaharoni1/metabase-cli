#!/usr/bin/env bash
# Load Metabase credentials: ~/.metabase.env (global) then .env.metabase, .env (project overrides).
# Source from project config scripts. Requires REPO_ROOT or run from project root.
REPO_ROOT="${REPO_ROOT:-$(pwd)}"
[[ -f "$HOME/.metabase.env" ]] && set -a && source "$HOME/.metabase.env" && set +a
[[ -f "$REPO_ROOT/.env.metabase" ]] && set -a && source "$REPO_ROOT/.env.metabase" && set +a
[[ -f "$REPO_ROOT/.env" ]] && set -a && source "$REPO_ROOT/.env" && set +a
