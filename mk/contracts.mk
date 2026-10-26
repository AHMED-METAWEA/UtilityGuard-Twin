# T-A1-002: contracts. Joins the shared CI list (see mk/ci.mk).
.PHONY: test-contracts
test-contracts:
	$(VPY) -m pytest platform/tests/contract -q
CI_TARGETS += test-contracts
