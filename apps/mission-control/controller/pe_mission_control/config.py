from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    execution_mode: str
    persona_engineering_root: Path | None
    python_executable: str
    data_dir: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        raw_mode = os.getenv("PE_MC_EXECUTION_MODE", "fixture").strip().lower()
        if raw_mode not in {"fixture", "real"}:
            raise ValueError("PE_MC_EXECUTION_MODE must be 'fixture' or 'real'")

        root_value = os.getenv("PERSONA_ENGINEERING_ROOT", "").strip()
        default_data = Path(__file__).resolve().parents[1] / "data"

        return cls(
            host=os.getenv("PE_MC_HOST", "127.0.0.1"),
            port=int(os.getenv("PE_MC_PORT", "8765")),
            execution_mode=raw_mode,
            persona_engineering_root=Path(root_value).expanduser()
            if root_value
            else None,
            python_executable=os.getenv("PE_MC_PYTHON", "python3"),
            data_dir=Path(os.getenv("PE_MC_DATA_DIR", str(default_data))).expanduser(),
        )
