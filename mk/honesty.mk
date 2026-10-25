.PHONY: test-honesty mutation-check

test-honesty:
	$(VPY) -m pytest platform/tests/honesty -q

# Guards the guards: applies eleven mutations in a scratch copy and fails unless the honesty
# suite catches every one (about 10 seconds).
mutation-check:
	bash scripts/mutation_check.sh

CI_TARGETS += test-honesty mutation-check
