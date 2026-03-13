import pytest

from tests.conftest import SITE_URL, LIST_NAME, call_tool

pytestmark = pytest.mark.integration


async def test_list_tools(mcp_session, test_report):
    tools = await mcp_session.list_tools()
    tool_names = [t.name for t in tools.tools]
    expected = [
        "get_site_lists_tool",
        "discover_list_tool",
        "ingest_list_tool",
        "search_tool",
        "search_all_tool",
        "list_sources_tool",
        "remove_source_tool",
        "refresh_tool",
    ]
    for name in expected:
        assert name in tool_names, f"Missing tool: {name}"
    assert len(tool_names) == 8


async def test_get_site_lists(mcp_session, test_report):
    data, is_error = await call_tool(
        mcp_session, test_report, "get_site_lists_tool",
        {"site_url": SITE_URL},
    )
    assert not is_error
    assert data["site_url"] == SITE_URL
    assert data["count"] > 0
    assert len(data["lists"]) == data["count"]
    for sp_list in data["lists"]:
        assert "id" in sp_list
        assert "name" in sp_list


async def test_discover_list(mcp_session, test_report):
    data, is_error = await call_tool(
        mcp_session, test_report, "discover_list_tool",
        {"site_url": SITE_URL, "list_name": LIST_NAME},
    )
    assert not is_error
    assert data["list_name"] == LIST_NAME
    assert len(data["columns"]) > 0
    assert data["item_count"] > 0


async def test_ingest_list(ingested_via_mcp):
    assert ingested_via_mcp["status"] == "complete"
    assert ingested_via_mcp["records_processed"] > 0
    assert ingested_via_mcp["chunks_created"] >= ingested_via_mcp["records_processed"]


async def test_list_sources(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "list_sources_tool", {},
    )
    assert not is_error
    names = [s["name"] for s in data["sources"]]
    assert LIST_NAME in names
    for source in data["sources"]:
        if source["name"] == LIST_NAME:
            for key in ("name", "site_url", "list_name", "collection_name"):
                assert key in source, f"Missing key: {key}"


async def test_search_vpn(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "search_tool",
        {"query": "VPN connectivity", "source": LIST_NAME, "top_k": 5},
    )
    assert not is_error
    assert len(data["results"]) > 0


async def test_search_mailbox(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "search_tool",
        {"query": "mailbox full", "source": LIST_NAME, "top_k": 5},
    )
    assert not is_error
    assert len(data["results"]) > 0


async def test_search_laptop(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "search_tool",
        {"query": "laptop screen flickering", "source": LIST_NAME, "top_k": 5},
    )
    assert not is_error
    assert len(data["results"]) > 0


async def test_search_top_k(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "search_tool",
        {"query": "printer not working", "source": LIST_NAME, "top_k": 3},
    )
    assert not is_error
    assert len(data["results"]) <= 3


async def test_search_result_structure(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "search_tool",
        {"query": "software installation", "source": LIST_NAME, "top_k": 5},
    )
    assert not is_error
    assert len(data["results"]) > 0

    for r in data["results"]:
        assert "id" in r, "Result missing 'id'"
        assert "score" in r, "Result missing 'score'"
        assert isinstance(r["id"], str)
        assert isinstance(r["score"], (int, float))

    scores = [r["score"] for r in data["results"]]
    assert scores == sorted(scores, reverse=True), "Results not sorted by score descending"


async def test_search_all(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "search_all_tool",
        {"query": "VPN connectivity", "top_k": 3},
    )
    assert not is_error
    assert "results" in data
    assert "sources_searched" in data
    assert len(data["results"]) > 0


async def test_refresh_single(mcp_session, test_report, ingested_via_mcp):
    data, is_error = await call_tool(
        mcp_session, test_report, "refresh_tool",
        {"source": LIST_NAME},
    )
    assert not is_error
    assert "Refreshed" in data


async def test_remove_source(mcp_session, test_report, ingested_via_mcp):
    await call_tool(
        mcp_session, test_report, "ingest_list_tool",
        {
            "site_url": SITE_URL,
            "list_name": LIST_NAME,
            "sync_interval_minutes": 0,
        },
    )

    # Add a dummy source by ingesting again with a different name isn't possible,
    # so we test remove on the real source and re-ingest after
    # Actually, let's just verify remove works on a known source
    # The plan says: "Add dummy, remove it, verify gone"
    # But we can't add a dummy through MCP — ingest_list_tool always uses the real list name.
    # Instead: verify the source exists, remove it, verify gone, then re-ingest.

    sources_before, _ = await call_tool(
        mcp_session, test_report, "list_sources_tool", {},
    )
    names_before = [s["name"] for s in sources_before["sources"]]
    assert LIST_NAME in names_before

    data, is_error = await call_tool(
        mcp_session, test_report, "remove_source_tool",
        {"source": LIST_NAME},
    )
    assert not is_error
    assert "removed successfully" in data

    sources_after, _ = await call_tool(
        mcp_session, test_report, "list_sources_tool", {},
    )
    names_after = [s["name"] for s in sources_after["sources"]]
    assert LIST_NAME not in names_after
