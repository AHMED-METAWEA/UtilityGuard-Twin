.PHONY: test-honesty

test-honesty:
	$(VPY) -m pytest platform/tests/honesty -q

CI_TARGETS += test-honesty
