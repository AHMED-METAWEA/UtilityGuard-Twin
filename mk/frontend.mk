# T-A1-010: the frontend shell. Joins the shared CI list (see mk/ci.mk).
# `npm ci` installs exactly the lockfile (frontend/.npmrc: no install scripts, no audit call).
.PHONY: frontend-install test-frontend
frontend-install:
	cd frontend && npm ci

# Type-check, unit and component tests, production build, then the offline check on the build.
test-frontend: frontend-install
	cd frontend && npm run check

CI_TARGETS += test-frontend
