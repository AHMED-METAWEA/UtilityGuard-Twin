# T-A1-005: domain adapter checks. Both join the shared CI list (see mk/ci.mk).
.PHONY: lint-imports test-conformance
lint-imports:
	$(VPY) scripts/check_imports.py
test-conformance:
	$(VPY) -m pytest platform/tests/conformance -q
CI_TARGETS += lint-imports test-conformance
