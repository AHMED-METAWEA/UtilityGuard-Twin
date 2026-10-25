# T-A1-008: the WNTR API manifest. Both targets join the shared CI list (see mk/ci.mk).
.PHONY: wntr-manifest wntr-manifest-write test-water
wntr-manifest:
	$(VPY) scripts/gen_wntr_manifest.py --check
wntr-manifest-write:
	$(VPY) scripts/gen_wntr_manifest.py --write
test-water:
	$(VPY) -m pytest domains/water/tests -q
CI_TARGETS += wntr-manifest test-water
