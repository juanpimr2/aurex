from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "bot-centralizado" / "frontend" / "src"
BACKEND_SRC = ROOT / "bot-centralizado" / "backend"

FRONTEND_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".vue"}
MUTATING_HTTP_METHODS = {"post", "put", "patch", "delete"}
ALLOWED_FRONTEND_MUTATION_ENDPOINTS = {"/api/backtest"}

FRONTEND_FORBIDDEN_TOKENS = {
    "/api/start",
    "/api/stop",
    "startBot",
    "stopBot",
    "open_position",
    "modify_position",
    "close_position",
}

BROKER_MUTATION_METHODS = {
    "open_position",
    "modify_position",
    "close_position",
}

APPROVED_BROKER_MUTATION_CALLERS = {
    Path("bot-centralizado/backend/monitor_swing.py"),
    Path("bot-centralizado/backend/monitor_scalp.py"),
    Path("bot-centralizado/backend/monitor_m15_obs.py"),
    Path("bot-centralizado/backend/legacy/main.py"),
    Path("bot-centralizado/backend/legacy/open_trade.py"),
    Path("bot-centralizado/backend/legacy/trader.py"),
}

MUTATING_ROUTE_METHOD_RE = re.compile(
    r"@app\.route\((?P<body>.*?)\)",
    re.DOTALL,
)
AXIOS_MUTATION_RE = re.compile(
    r"axios\.(?P<method>post|put|patch|delete)\(\s*['\"](?P<endpoint>[^'\"]+)",
    re.IGNORECASE,
)
FETCH_MUTATION_RE = re.compile(
    r"fetch\(\s*['\"](?P<endpoint>[^'\"]+)['\"].*?method\s*:\s*['\"](?P<method>POST|PUT|PATCH|DELETE)['\"]",
    re.IGNORECASE | re.DOTALL,
)
BROKER_CALL_RE = re.compile(
    r"\.\s*(?P<method>open_position|modify_position|close_position)\s*\("
)


def rel(path: Path) -> Path:
    return path.resolve().relative_to(ROOT)


def add_violation(violations: list[str], path: Path, line: int | None, message: str) -> None:
    location = str(rel(path)).replace("\\", "/")
    if line is not None:
        location = f"{location}:{line}"
    violations.append(f"{location}: {message}")


def line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def check_frontend(violations: list[str]) -> None:
    if not FRONTEND_SRC.exists():
        add_violation(violations, FRONTEND_SRC, None, "frontend source directory is missing")
        return

    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in FRONTEND_SUFFIXES or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")

        for token in FRONTEND_FORBIDDEN_TOKENS:
            offset = content.find(token)
            if offset != -1:
                add_violation(
                    violations,
                    path,
                    line_number(content, offset),
                    f"frontend must not expose live trading token `{token}`",
                )

        for match in AXIOS_MUTATION_RE.finditer(content):
            method = match.group("method").lower()
            endpoint = match.group("endpoint")
            if method in MUTATING_HTTP_METHODS and endpoint not in ALLOWED_FRONTEND_MUTATION_ENDPOINTS:
                add_violation(
                    violations,
                    path,
                    line_number(content, match.start()),
                    f"frontend mutating request `{method.upper()} {endpoint}` is not allowed",
                )

        for match in FETCH_MUTATION_RE.finditer(content):
            endpoint = match.group("endpoint")
            method = match.group("method").upper()
            if endpoint not in ALLOWED_FRONTEND_MUTATION_ENDPOINTS:
                add_violation(
                    violations,
                    path,
                    line_number(content, match.start()),
                    f"frontend mutating fetch `{method} {endpoint}` is not allowed",
                )


def check_dashboard_routes(violations: list[str]) -> None:
    dashboard = BACKEND_SRC / "dashboard.py"
    if not dashboard.exists():
        add_violation(violations, dashboard, None, "dashboard.py is missing")
        return

    content = dashboard.read_text(encoding="utf-8")
    for method in BROKER_MUTATION_METHODS:
        offset = content.find(method)
        if offset != -1:
            add_violation(
                violations,
                dashboard,
                line_number(content, offset),
                f"dashboard must not call broker mutation `{method}`",
            )

    for match in MUTATING_ROUTE_METHOD_RE.finditer(content):
        body = match.group("body")
        route_match = re.search(r"['\"](?P<route>/api/[^'\"]*)['\"]", body)
        if not route_match:
            continue
        route = route_match.group("route")
        methods = {m.upper() for m in re.findall(r"['\"](POST|PUT|PATCH|DELETE)['\"]", body, re.I)}
        if methods:
            add_violation(
                violations,
                dashboard,
                line_number(content, match.start()),
                f"dashboard route `{route}` exposes mutating methods {sorted(methods)}",
            )


def check_runtime_status(violations: list[str]) -> None:
    runtime_status = BACKEND_SRC / "runtime_status.py"
    if not runtime_status.exists():
        add_violation(violations, runtime_status, None, "runtime_status.py is missing")
        return

    content = runtime_status.read_text(encoding="utf-8")
    for method in BROKER_MUTATION_METHODS:
        offset = content.find(method)
        if offset != -1:
            add_violation(
                violations,
                runtime_status,
                line_number(content, offset),
                f"runtime status contract must not reference broker mutation `{method}`",
            )


def check_broker_mutation_callers(violations: list[str]) -> None:
    for path in BACKEND_SRC.rglob("*.py"):
        if "\\tests\\" in str(path):
            continue
        content = path.read_text(encoding="utf-8")
        relative = rel(path)

        for match in BROKER_CALL_RE.finditer(content):
            if relative in APPROVED_BROKER_MUTATION_CALLERS:
                continue
            add_violation(
                violations,
                path,
                line_number(content, match.start()),
                f"unexpected broker mutation call `{match.group('method')}`",
            )


def main() -> int:
    violations: list[str] = []

    check_frontend(violations)
    check_dashboard_routes(violations)
    check_runtime_status(violations)
    check_broker_mutation_callers(violations)

    if violations:
        print("Read-only contract violations found:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Read-only contract check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
