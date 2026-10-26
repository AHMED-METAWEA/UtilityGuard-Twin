# UtilityGuard Twin: root Makefile.
# Each task card adds its own targets in mk/<name>.mk (included below), so cards running in
# parallel never edit the same file. Keep this file to the shared variables and `install`.

PYTHON ?= python3.11
VENV   ?= .venv
VPY    := $(VENV)/bin/python

# Installable projects, installed one by one in editable mode (platform/ is a folder, not a package).
PACKAGES := platform/ug_core platform/ug_intel platform/ug_api platform/ug_cli domains/water

.PHONY: install check-layout help

help:
	@echo "make install       create $(VENV) with $(PYTHON) and install every package in editable mode"
	@echo "make check-layout  verify the repository layout against Master Spec section 14"

# The interpreter's bundled pip and setuptools carry known vulnerabilities (task T-B1-002, found by
# `make audit-python`): every `make install`, also on an existing .venv, pins pip to a fixed release
# that is at least 14 days old and removes setuptools, which nothing here needs at run or test time
# (package builds use an isolated build environment). Both steps are idempotent.
PIP_VERSION := 26.2.1

$(VPY):
	$(PYTHON) -m venv $(VENV)

install: $(VPY)
	$(VPY) -m pip install --disable-pip-version-check --quiet "pip==$(PIP_VERSION)"
	$(VPY) -m pip uninstall --disable-pip-version-check --quiet --yes setuptools
	$(VPY) -m pip install --disable-pip-version-check --quiet --constraint constraints/runtime.txt --build-constraint constraints/build.txt $(addprefix -e ,$(PACKAGES))
	@echo "installed: $(PACKAGES)"

check-layout:
	python3 scripts/check_layout.py

-include mk/*.mk
