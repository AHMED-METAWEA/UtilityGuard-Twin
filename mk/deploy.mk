# T-A1-011: same-origin shell/API deployment.
.PHONY: deploy-config up up-wait down logs smoke container-check

CI_TARGETS += deploy-config

deploy-config:
	@if command -v docker >/dev/null 2>&1; then \
		docker compose -f deploy/docker-compose.yml config -q; \
	else \
		echo "SKIPPED deploy-config: docker is not installed (ug doctor warns about it)"; \
	fi

up:
	docker compose -f deploy/docker-compose.yml up --build -d
	@echo "http://127.0.0.1:8080/"

down:
	docker compose -f deploy/docker-compose.yml down

logs:
	docker compose -f deploy/docker-compose.yml logs -f

smoke:
	bash deploy/smoke.sh

# Waits until the container reports healthy (Compose v2 `--wait`), for scripts and CI.
up-wait:
	docker compose -f deploy/docker-compose.yml up -d --wait --wait-timeout 120

# Checks the hardening of the running container (T-B1-001).
container-check:
	bash deploy/check_container.sh
