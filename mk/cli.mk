# T-A1-009: offline environment diagnostics.
.PHONY: doctor
doctor:
	$(VPY) -m ug_cli doctor
CI_TARGETS += doctor
