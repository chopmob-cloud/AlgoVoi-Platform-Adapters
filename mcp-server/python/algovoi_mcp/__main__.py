"""Entry point for ``python -m algovoi_mcp`` and the ``algovoi-mcp`` script."""

import asyncio

from .server import run_stdio


def main() -> None:
    try:
        asyncio.run(run_stdio())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
