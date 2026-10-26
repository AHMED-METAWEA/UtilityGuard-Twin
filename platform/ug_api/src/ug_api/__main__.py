"""Launch the API with explicit environment configuration."""

import os
import re
from pathlib import Path

import uvicorn

from ug_api.app import create_app


def main() -> None:
    raw_port = os.environ.get("UG_API_PORT", "8080")
    message = "UG_API_PORT must be an integer from 1 to 65535"
    try:
        port = int(raw_port)
    except ValueError:
        raise SystemExit(message) from None
    if not re.fullmatch(r"[0-9]+", raw_port) or not 1 <= port <= 65535:
        raise SystemExit(message)
    static_dir = os.environ.get("UG_STATIC_DIR")
    uvicorn.run(
        create_app(Path(static_dir) if static_dir else None),
        host=os.environ.get("UG_API_HOST", "127.0.0.1"),
        port=port,
        reload=False,
        access_log=True,
        server_header=False,
    )


if __name__ == "__main__":
    main()
