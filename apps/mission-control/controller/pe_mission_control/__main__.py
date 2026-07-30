from __future__ import annotations

import uvicorn

from .config import Settings


def main() -> None:
    settings = Settings.from_environment()
    uvicorn.run(
        "pe_mission_control.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
