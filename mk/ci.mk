.PHONY: install-dev lint typecheck test-unit ci

install-dev: install
	$(VPY) -m pip install --disable-pip-version-check --constraint constraints/runtime.txt -r requirements-dev.txt

lint:
	$(VPY) -m ruff check .
	$(VPY) -m ruff format --check .

typecheck:
	$(VPY) -m mypy platform/ug_core/src platform/ug_intel/src platform/ug_api/src platform/ug_cli/src domains/water/src

test-unit:
	$(VPY) -m pytest platform/tests/unit -q

# Each card registers its checks in its own mk/*.mk file, for example:
# CI_TARGETS += test-contracts
# Keep this registry additive. Expand it in the recipe, not prerequisites,
# so targets registered by files included after this one run locally and in CI.
CI_TARGETS += lint typecheck test-unit

ci:
	$(MAKE) --no-print-directory $(CI_TARGETS)
