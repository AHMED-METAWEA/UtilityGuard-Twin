# T-A1-014: the browser test. Opens the built shell in a real Chromium (Playwright, pinned in
# frontend/package.json) and proves that it makes no request to another origin.
# `make browser-install` downloads the matching Chromium build once (about 100 MB, into the user
# cache, outside the repository). CI uses `--with-deps` for the system libraries (see ci.yml).
# Joins the shared CI list (see mk/ci.mk).
.PHONY: browser-install test-browser
browser-install: frontend-install
	cd frontend && npx playwright install chromium

test-browser: frontend-install
	cd frontend && npx vite build && npx playwright test

CI_TARGETS += test-browser
