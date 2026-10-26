# T-B1-002: known vulnerabilities in the Python packages we install, from PyPI's advisory data.
# Needs network access to pypi.org, so it is not part of `make ci`; hosted CI runs both targets
# as the `audit` job. Exit codes: 0 clean, 1 vulnerable, 2 incomplete (see scripts/audit_python.py).
.PHONY: audit-python audit-image

AUDIT_IGNORE := scripts/audit_python_ignore.txt

# The container's locked runtime set and everything installed in the development environment.
audit-python:
	$(VPY) scripts/audit_python.py --lock deploy/requirements-api.lock --installed --ignore $(AUDIT_IGNORE)

# Everything installed in the built image, audited by the image's own Python (standard library only).
audit-image:
	docker build --quiet -f deploy/Dockerfile -t ug-audit-image . >/dev/null
	docker run --rm --entrypoint python -v "$(CURDIR)/scripts:/audit:ro" ug-audit-image \
		/audit/audit_python.py --installed --ignore /audit/$(notdir $(AUDIT_IGNORE))
