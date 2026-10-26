#!/usr/bin/env bash
# Checks that the running `app` container keeps the hardening of deploy/docker-compose.yml and
# deploy/Dockerfile: non-root user 10001, read-only root filesystem, every capability dropped,
# none added back, not privileged, no privilege gain, and port 8080 published on host loopback
# only. Run after `make up`.
# Prints one PASS or FAIL line per check and exits non-zero on any failure.
set -euo pipefail

compose=(docker compose -f "$(dirname "${BASH_SOURCE[0]}")/docker-compose.yml")
cid="$("${compose[@]}" ps -q app)"
if [ -z "$cid" ]; then
  echo "FAIL container: no running app container (run make up first)"
  exit 1
fi

failed=0
check() { # name expected actual
  if [ "$2" = "$3" ]; then
    echo "PASS $1"
  else
    echo "FAIL $1: expected '$2', got '$3'"
    failed=1
  fi
}

check "runs as uid 10001" "10001" "$(docker inspect -f '{{.Config.User}}' "$cid")"
check "read-only root filesystem" "true" "$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$cid")"
check "every capability dropped" '["ALL"]' "$(docker inspect -f '{{json .HostConfig.CapDrop}}' "$cid")"
check "no capability added back" "null" "$(docker inspect -f '{{json .HostConfig.CapAdd}}' "$cid")"
check "not privileged" "false" "$(docker inspect -f '{{.HostConfig.Privileged}}' "$cid")"
check "no privilege gain" '["no-new-privileges:true"]' "$(docker inspect -f '{{json .HostConfig.SecurityOpt}}' "$cid")"
check "port 8080 on host loopback only" "127.0.0.1:8080" "$(docker port "$cid" 8080/tcp | sort -u | tr '\n' ' ' | sed 's/ $//')"
check "health" "healthy" "$(docker inspect -f '{{.State.Health.Status}}' "$cid")"
uid_inside="$(docker exec "$cid" id -u)"
check "process uid inside the container" "10001" "$uid_inside"
exit "$failed"
