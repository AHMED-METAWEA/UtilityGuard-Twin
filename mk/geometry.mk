# T-B1-010: public street geometry. These targets need network access to the Overpass API, so
# they are not part of `make ci`. The extract stays in the git-ignored data/geometry/ (G2).
.PHONY: fetch-geometry-live geometry-report

# Fetch a new extract of the capital study box and write its coverage report.
fetch-geometry-live:
	$(VPY) -m ug_cli fetch-geometry --area capital --refresh --report

# Rewrite the coverage report from the newest cached extract, offline.
geometry-report:
	$(VPY) -m ug_cli fetch-geometry --area capital --offline --report
