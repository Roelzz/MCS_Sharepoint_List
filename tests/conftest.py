import json
import multiprocessing
import shutil
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

import pytest

SITE_URL = "https://copilotstudiotraining-my.sharepoint.com/personal/roel_schenk_copilotstudiotraining_onmicrosoft_com"
LIST_NAME = "vector_search_test_data"
SERVER_PORT = 8081


def _find_dotenv() -> str | None:
    """Find .env by walking up from this file's directory."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / ".env"
        if candidate.is_file():
            return str(candidate)
        current = current.parent
    return None


def _run_server(data_dir: str) -> None:
    """Top-level function for multiprocessing (must be picklable on macOS spawn)."""
    import os

    from dotenv import load_dotenv

    dotenv_path = _find_dotenv()
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)

    os.environ["DATA_DIR"] = data_dir
    os.environ["MCP_TRANSPORT"] = "sse"
    os.environ["MCP_PORT"] = str(SERVER_PORT)

    from src.server import mcp

    mcp.run(transport="sse", port=SERVER_PORT)


def _wait_for_server(port: int, timeout: float = 15.0) -> None:
    """Poll server until it responds or timeout."""
    deadline = time.monotonic() + timeout
    url = f"http://localhost:{port}/sse"
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
        except urllib.error.URLError:
            time.sleep(0.3)
            continue
        except Exception:
            return
        return
    raise RuntimeError(f"Server on port {port} not ready after {timeout}s")


@pytest.fixture(scope="session")
def temp_data_dir():
    tmp = Path(tempfile.mkdtemp(prefix="sp_mcp_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def mcp_server(temp_data_dir: Path):
    proc = multiprocessing.Process(
        target=_run_server,
        args=(str(temp_data_dir),),
        daemon=True,
    )
    proc.start()
    try:
        _wait_for_server(SERVER_PORT)
    except RuntimeError:
        proc.terminate()
        proc.join(5)
        raise
    yield proc
    proc.terminate()
    proc.join(5)
    if proc.is_alive():
        proc.kill()
        proc.join(2)


@pytest.fixture(scope="session")
async def mcp_session(mcp_server):
    from contextlib import AsyncExitStack

    from mcp import ClientSession
    from mcp.client.sse import sse_client

    url = f"http://localhost:{SERVER_PORT}/sse"
    stack = AsyncExitStack()
    read_stream, write_stream = await stack.enter_async_context(sse_client(url))
    session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
    await session.initialize()
    yield session
    # Teardown: suppress the cross-task cancel scope error from anyio
    try:
        await stack.aclose()
    except RuntimeError:
        pass


@pytest.fixture(scope="session")
async def ingested_via_mcp(mcp_session, test_report):
    data, is_error = await call_tool(
        mcp_session,
        test_report,
        "ingest_list_tool",
        {
            "site_url": SITE_URL,
            "list_name": LIST_NAME,
            "sync_interval_minutes": 0,
        },
    )
    assert not is_error, f"Ingest failed: {data}"
    return data


@pytest.fixture(scope="session")
def test_report():
    results: list[dict] = []
    yield results
    _write_report(results)


async def call_tool(
    session, report: list[dict], tool_name: str, params: dict
) -> tuple[dict | str, bool]:
    """Call an MCP tool, parse response, record in report."""
    response = await session.call_tool(tool_name, params)
    is_error = response.isError if hasattr(response, "isError") else False

    raw_text = response.content[0].text if response.content else ""
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        parsed = raw_text

    report.append(
        {
            "tool": tool_name,
            "params": params,
            "response": parsed,
            "is_error": is_error,
            "status": "FAIL" if is_error else "PASS",
        }
    )
    return parsed, is_error


def _write_report(results: list[dict]) -> None:
    """Write markdown report to tests/test_results.md."""
    report_path = Path(__file__).parent / "test_results.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# E2E Test Results",
        f"Generated: {now}",
        "",
        "| # | Tool | Status | Response (truncated) |",
        "|---|------|--------|---------------------|",
    ]
    for i, r in enumerate(results, 1):
        resp_str = json.dumps(r["response"]) if isinstance(r["response"], dict) else str(r["response"])
        truncated = resp_str[:100] + "..." if len(resp_str) > 100 else resp_str
        lines.append(f"| {i} | {r['tool']} | {r['status']} | {truncated} |")

    lines.extend(["", "## Detailed Results", ""])
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r['tool']}")
        lines.append("**Parameters:**")
        lines.append(f"```json\n{json.dumps(r['params'], indent=2)}\n```")
        lines.append("**Response:**")
        resp = json.dumps(r["response"], indent=2) if isinstance(r["response"], dict) else str(r["response"])
        lines.append(f"```json\n{resp}\n```")
        lines.append(f"**Status:** {r['status']}")
        lines.append("")

    report_path.write_text("\n".join(lines))
