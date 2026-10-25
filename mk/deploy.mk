# T-A1-011: same-origin shell/API deployment.
.PHONY: deploy-config up down logs smoke

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
