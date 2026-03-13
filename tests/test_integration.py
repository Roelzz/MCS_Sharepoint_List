import pytest

from src.tools.discover import discover_list_schema
from src.tools.search import search_list
from src.tools.manage import source_manager

from tests.conftest import SITE_URL, LIST_NAME

pytestmark = pytest.mark.integration


# --- Discover tests ---


async def test_discover_list_schema():
    result = await discover_list_schema(SITE_URL, LIST_NAME)

    assert result.list_name == LIST_NAME
    assert result.item_count > 0

    display_names = [c.display_name for c in result.columns]
    expected = ["Title", "Description", "Category", "Priority", "Status",
                "Resolution", "SubmittedBy", "Department", "Location"]
    for col in expected:
        assert col in display_names, f"Missing column: {col}"


async def test_discover_list_tool_wrapper():
    from src.server import discover_list_tool

    result = await discover_list_tool(SITE_URL, LIST_NAME)
    assert isinstance(result, dict)
    assert "list_name" in result
    assert "columns" in result


# --- Ingest tests ---


async def test_ingest_list(ingested_source: dict):
    assert ingested_source["status"] == "complete"
    assert ingested_source["records_processed"] > 0
    assert ingested_source["chunks_created"] >= ingested_source["records_processed"]


# --- Source management tests ---


async def test_list_sources_after_ingest(ingested_source: dict):
    sources = source_manager.list_sources()
    names = [s["name"] for s in sources["sources"]]
    assert LIST_NAME in names


# --- Semantic search tests ---


async def test_search_vpn_connectivity(ingested_source: dict):
    result = await search_list(
        "VPN connectivity issues",
        ingested_source["collection_name"],
        top_k=5,
    )
    texts = _result_texts(result)
    assert any(
        term in texts for term in ["vpn", "network", "connectivity"]
    ), f"No VPN-related results in: {texts[:200]}"


async def test_search_mailbox_full(ingested_source: dict):
    result = await search_list(
        "mailbox full",
        ingested_source["collection_name"],
        top_k=5,
    )
    texts = _result_texts(result)
    assert any(
        term in texts for term in ["email", "mailbox", "inbox"]
    ), f"No email-related results in: {texts[:200]}"


async def test_search_laptop_screen(ingested_source: dict):
    result = await search_list(
        "laptop screen flickering",
        ingested_source["collection_name"],
        top_k=5,
    )
    texts = _result_texts(result)
    assert any(
        term in texts for term in ["screen", "display", "hardware", "monitor"]
    ), f"No screen-related results in: {texts[:200]}"


async def test_search_teams_access(ingested_source: dict):
    result = await search_list(
        "can't access Teams",
        ingested_source["collection_name"],
        top_k=5,
    )
    texts = _result_texts(result)
    assert any(
        term in texts for term in ["teams", "access", "permissions"]
    ), f"No Teams-related results in: {texts[:200]}"


async def test_search_password_reset(ingested_source: dict):
    result = await search_list(
        "password reset",
        ingested_source["collection_name"],
        top_k=5,
    )
    texts = _result_texts(result)
    assert any(
        term in texts for term in ["password", "credentials", "sign-in", "sign_in"]
    ), f"No password-related results in: {texts[:200]}"


# --- Search behavior tests ---


async def test_search_top_k_respected(ingested_source: dict):
    result = await search_list(
        "printer not working",
        ingested_source["collection_name"],
        top_k=3,
    )
    assert len(result["results"]) <= 3


async def test_search_result_structure(ingested_source: dict):
    result = await search_list(
        "software installation",
        ingested_source["collection_name"],
        top_k=5,
    )
    assert len(result["results"]) > 0

    for r in result["results"]:
        assert "id" in r, "Result missing 'id'"
        assert "score" in r, "Result missing 'score'"
        assert isinstance(r["id"], str)
        assert isinstance(r["score"], (int, float))

    scores = [r["score"] for r in result["results"]]
    assert scores == sorted(scores, reverse=True), "Results not sorted by score descending"


async def test_search_tool_wrapper(ingested_source: dict):
    from src.server import search_tool

    result = await search_tool(
        query="network issue",
        source=LIST_NAME,
        top_k=3,
    )
    assert isinstance(result, dict)
    assert "results" in result
    assert "source" in result
    assert "query" in result


# --- Cleanup test ---


async def test_remove_source(ingested_source: dict):
    source_manager.add_source({
        "name": "cleanup_test_source",
        "site_url": SITE_URL,
        "list_name": LIST_NAME,
        "collection_name": ingested_source["collection_name"] + "_cleanup_test",
        "sync_interval_minutes": 0,
        "column_overrides": {},
    })

    sources_before = source_manager.list_sources()
    names_before = [s["name"] for s in sources_before["sources"]]
    assert "cleanup_test_source" in names_before

    source_manager.remove_source("cleanup_test_source")

    sources_after = source_manager.list_sources()
    names_after = [s["name"] for s in sources_after["sources"]]
    assert "cleanup_test_source" not in names_after


# --- Helpers ---


def _result_texts(result: dict) -> str:
    parts = []
    for r in result.get("results", []):
        parts.append(str(r.get("content", "")))
        parts.append(str(r.get("id", "")))
        if "metadata" in r:
            parts.append(str(r["metadata"]))
    return " ".join(parts).lower()
