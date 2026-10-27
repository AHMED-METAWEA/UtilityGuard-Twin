.PHONY: status

status:
	.venv/bin/python scripts/status.py --gh --write docs/STATUS.md
