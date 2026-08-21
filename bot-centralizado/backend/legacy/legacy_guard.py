# -*- coding: utf-8 -*-
import os


def legacy_runtime_allowed() -> bool:
    return os.getenv("AUREX_ALLOW_LEGACY_RUNTIME", "").strip().upper() == "YES"


def legacy_block_reason(name: str) -> str:
    return (
        name + " is legacy and disabled by default. "
        "Set AUREX_ALLOW_LEGACY_RUNTIME=YES only for an isolated lab run."
    )


def require_legacy_runtime(name: str) -> None:
    if not legacy_runtime_allowed():
        raise RuntimeError(legacy_block_reason(name))
