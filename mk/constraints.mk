.PHONY: constraints check-constraints

constraints:
	$(VPY) scripts/gen_constraints.py

check-constraints:
	$(VPY) scripts/gen_constraints.py --check

CI_TARGETS += check-constraints
