#!/usr/bin/env bash
#
# End-to-end check with curl against a real server, including a restart.
#
#   scripts/smoke.sh                       start a private server on a free port, test, restart, test again
#   BASE_URL=http://127.0.0.1:8000 scripts/smoke.sh
#                                          test a server you already started (skips the restart step)
#
# Needs: bash, curl, python3 (for JSON checks). Exits non-zero on the first failed check.
# The users it registers get a random suffix, so it can run repeatedly against one server.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="$ROOT/taskmanager"
if [ -z "${PYTHON:-}" ]; then
  if [ -x "$ROOT/.venv/bin/python" ]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON="python3"; fi
fi

SERVER_PID=""
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/taskmanager-smoke.XXXXXX")"
cleanup() {
  if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

TOKEN=""
# request METHOD PATH [json body]  -> sets STATUS and BODY; sends the current TOKEN if any
request() {
  local method="$1" path="$2" body="${3:-}" out
  local args=(-sS -o - -w '\n%{http_code}' -X "$method" -H 'Content-Type: application/json')
  if [ -n "$TOKEN" ]; then args+=(-H "Authorization: Bearer $TOKEN"); fi
  if [ -n "$body" ]; then args+=(--data "$body"); fi
  out="$(curl "${args[@]}" "$BASE_URL$path")"
  STATUS="${out##*$'\n'}"
  BODY="${out%$'\n'*}"
}

expect_status() { [ "$STATUS" = "$1" ] || fail "expected HTTP $1, got $STATUS: $BODY"; }

# json_check "python expression using data"   (data = parsed BODY)
json_check() {
  printf '%s' "$BODY" | "$PYTHON" -c "import json,sys; data=json.load(sys.stdin); ok=bool($1); sys.exit(0 if ok else 1)" \
    || fail "check '$1' failed on: $BODY"
}

json_get() { printf '%s' "$BODY" | "$PYTHON" -c "import json,sys; data=json.load(sys.stdin); print($1)"; }

start_server() {
  export TASKMANAGER_DATA_DIR="$TMP_DIR/data"
  ( cd "$PROJECT" && "$PYTHON" manage.py migrate --noinput -v 0 )
  # exec so that $! is the server itself, not a wrapper shell (otherwise the server would outlive us)
  ( cd "$PROJECT" && exec "$PYTHON" manage.py runserver "127.0.0.1:$PORT" --noreload >"$TMP_DIR/server.log" 2>&1 ) &
  SERVER_PID=$!
  for _ in $(seq 1 50); do
    if curl -sf "$BASE_URL/health/" >/dev/null 2>&1; then return 0; fi
    sleep 0.2
  done
  cat "$TMP_DIR/server.log" >&2
  fail "server did not come up on $BASE_URL"
}

stop_server() {
  kill "$SERVER_PID"; wait "$SERVER_PID" 2>/dev/null || true; SERVER_PID=""
}

MANAGED=0
if [ -z "${BASE_URL:-}" ]; then
  MANAGED=1
  PORT="$("$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
  BASE_URL="http://127.0.0.1:$PORT"
  step "starting a private server on $BASE_URL (data in $TMP_DIR/data)"
  start_server
fi
echo "using $BASE_URL"

SUFFIX="$(date +%s)$RANDOM"
ALICE="alice$SUFFIX"
BOB="bob$SUFFIX"
PASSWORD="correct-horse-battery"

step "health and index are public"
request GET /health/; expect_status 200; json_check 'data["status"] == "ok"'
request GET /; expect_status 200; json_check '"/tasks/" in data["endpoints"]'

step "anonymous requests are refused"
request GET /tasks/; expect_status 401; json_check 'data["code"] == "not_authenticated"'

step "register two users"
request POST /auth/register/ "{\"username\": \"$ALICE\", \"password\": \"$PASSWORD\", \"first_name\": \"Alice\"}"
expect_status 201; json_check 'data["username"] == "'"$ALICE"'" and "password" not in data'
request POST /auth/register/ "{\"username\": \"$BOB\", \"password\": \"$PASSWORD\", \"first_name\": \"Bob\"}"
expect_status 201; BOB_ID="$(json_get 'data["id"]')"
request POST /auth/register/ "{\"username\": \"$BOB\", \"password\": \"$PASSWORD\"}"
expect_status 400; json_check '"username" in data'

step "sign in as alice (JWT)"
request POST /auth/token/ "{\"username\": \"$ALICE\", \"password\": \"$PASSWORD\"}"
expect_status 200; json_check '"access" in data and "refresh" in data'
TOKEN="$(json_get 'data["access"]')"
REFRESH="$(json_get 'data["refresh"]')"
request GET /auth/me/; expect_status 200; json_check 'data["username"] == "'"$ALICE"'"'
request POST /auth/token/refresh/ "{\"refresh\": \"$REFRESH\"}"; expect_status 200; json_check '"access" in data'

step "the user directory"
request GET "/users/?search=$BOB"; expect_status 200; json_check 'data["count"] == 1 and data["results"][0]["id"] == '"$BOB_ID"

step "create a task"
request POST /tasks/ '{"title": "Write the report", "description": "Q3 numbers", "due_date": "2026-09-12"}'
expect_status 201; TASK_ID="$(json_get 'data["id"]')"
json_check 'data["status"] == "todo" and data["assignee"] is None and data["completed_at"] is None'
json_check 'data["creator"]["username"] == "'"$ALICE"'"'
echo "task id: $TASK_ID"
request POST /tasks/ '{"title": ""}'; expect_status 400; json_check '"title" in data'

step "assign it to bob"
request POST "/tasks/$TASK_ID/assign/" "{\"assignee_id\": $BOB_ID}"
expect_status 200; json_check 'data["assignee"]["id"] == '"$BOB_ID"
request POST "/tasks/$TASK_ID/assign/" '{"assignee_id": 999999}'; expect_status 400

step "edit it"
request PATCH "/tasks/$TASK_ID/" '{"status": "in_progress", "title": "Write the Q3 report"}'
expect_status 200; json_check 'data["status"] == "in_progress" and data["title"] == "Write the Q3 report"'

step "list and filter"
request GET /tasks/; expect_status 200; json_check 'data["count"] >= 1 and data["results"][0]["id"] == '"$TASK_ID"
request GET "/tasks/?assignee=$BOB_ID&status=in_progress"; expect_status 200; json_check 'data["count"] == 1'
request GET "/tasks/?status=done&creator=me"; expect_status 200; json_check 'data["count"] == 0'
request GET "/tasks/?status=later"; expect_status 400; json_check '"status" in data'

step "sign in as bob and comment"
ALICE_TOKEN="$TOKEN"
request POST /auth/token/ "{\"username\": \"$BOB\", \"password\": \"$PASSWORD\"}"; expect_status 200
TOKEN="$(json_get 'data["access"]')"
request POST "/tasks/$TASK_ID/comments/" '{"text": "On it, done by Friday"}'
expect_status 201; COMMENT_ID="$(json_get 'data["id"]')"
json_check 'data["author"]["username"] == "'"$BOB"'"'
request GET "/tasks/$TASK_ID/comments/"; expect_status 200; json_check 'data["count"] == 1'
request GET "/tasks/$TASK_ID/"; expect_status 200; json_check 'data["comment_count"] == 1'

step "bob (the assignee) completes the task but may not delete it"
request POST "/tasks/$TASK_ID/complete/"; expect_status 200
json_check 'data["status"] == "done" and data["completed_at"] is not None'
request DELETE "/tasks/$TASK_ID/"; expect_status 403; json_check 'data["code"] == "permission_denied"'

step "alice may not edit bob's comment"
TOKEN="$ALICE_TOKEN"
request PATCH "/tasks/$TASK_ID/comments/$COMMENT_ID/" '{"text": "changed"}'; expect_status 403

if [ "$MANAGED" = 1 ]; then
  step "restart the server and check everything survived"
  stop_server
  start_server
  request GET "/tasks/$TASK_ID/"; expect_status 200
  json_check 'data["status"] == "done" and data["assignee"]["id"] == '"$BOB_ID"' and data["comment_count"] == 1'
  request GET /auth/me/; expect_status 200; json_check 'data["username"] == "'"$ALICE"'"'
fi

step "alice deletes the task; the comments go with it"
request DELETE "/tasks/$TASK_ID/"; expect_status 204
request GET "/tasks/$TASK_ID/"; expect_status 404; json_check 'data["code"] == "not_found"'
request GET "/tasks/$TASK_ID/comments/"; expect_status 404

printf '\nSMOKE OK\n'
