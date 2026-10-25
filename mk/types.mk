.PHONY: types-install gen-types check-contract-drift

types-install:
	@if ! (cd scripts/types && npm ls --all --silent >/dev/null 2>&1); then \
		cd scripts/types && npm ci --ignore-scripts --no-audit --no-fund; \
	fi

gen-types: types-install
	node scripts/gen_types.mjs

check-contract-drift: types-install
	bash scripts/check_contract_drift.sh

CI_TARGETS += check-contract-drift
