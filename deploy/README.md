# Local deployment

`make up` builds the React/Vite shell and the FastAPI skeleton, then starts one
non-root container. Open http://127.0.0.1:8080/. Compose publishes port 8080 only
on host loopback; it is not exposed on other host interfaces. The shell and
`/api/health` share an origin so the shell's strict CSP remains in force.

Run `make smoke` after the container becomes healthy. This requires curl,
python3 and Node on the host and uses the repository's offline gate without
changing it. An alternate base URL can be passed to `bash deploy/smoke.sh URL`.
Use `make logs` to follow logs and `make down` to stop and remove the container.
`make deploy-config` validates Compose without building or starting anything.
Docker Compose v2 is required; builds need access to the image and package
registries. The two base images (`node:22-slim`, `python:3.11-slim`) are pinned
by digest in `deploy/Dockerfile` (read on 2026-10-25); moving to a newer digest
is a deliberate, reviewed change, so security updates of the base images are
not picked up automatically.

## API configuration

For a local Python process, `python -m ug_api` accepts:

| Variable | Default | Meaning |
| --- | --- | --- |
| `UG_API_HOST` | `127.0.0.1` | Bind address |
| `UG_API_PORT` | `8080` | Decimal integer from 1 through 65535 |
| `UG_STATIC_DIR` | unset | Existing directory to serve at `/` |

The image sets the host to `0.0.0.0` inside the container and the static directory
to `/srv/web`; Compose still binds only to host loopback. No static directory
means `/` returns a 404 problem response. Health reports the package version,
schema version and the shell's advisory disclaimer. API responses disable caching
and MIME sniffing. Documentation/OpenAPI routes are disabled.

The container serves local files and health only. It makes no outbound network
requests at run time and has no write path to equipment. It runs with a read-only
root filesystem, temporary `/tmp`, dropped capabilities and no privilege gain.
It has no application volumes, secrets or external networks. These settings do
not enforce an outbound firewall; offline behavior is checked by the smoke gate
and the shell CSP. Everything is advisory only: a human approves every action.
This virtual twin is not ACUD data or a survey of any real network and is not
certified for operation of critical infrastructure.

## Refreshing the runtime lock

Refresh only in an authorized network-enabled maintenance run. Keep explicit
FastAPI and uvicorn top-level pins within the API package's declared ranges.
Review PyPI release timestamps and choose the newest approved releases at least
14 days old, including all transitive dependencies. Build a constraints file
pinning eligible versions, resolve the top-level pins with pip using that
constraints file in a clean Python 3.11 environment, and record the exact
resolved dependency set. Obtain SHA-256 hashes from PyPI's file metadata for
those exact releases (wheels and source archives), and write each resolved
package as `name==version` with its `--hash=sha256:...` entries in
`deploy/requirements-api.lock`. Do not hand-invent hashes or omit transitives.
Verify a fresh `pip install --require-hashes -r deploy/requirements-api.lock`,
run the API tests and CI, rebuild the image, and have the lead run the Docker
smoke checks. Record the resolution date, release-age cutoff and approvals in
the lock review. This task preserves the lead-prepared lock unchanged.
