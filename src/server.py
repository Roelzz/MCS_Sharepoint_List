import traceback

from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.providers.azure import AzureProvider, EntraOBOToken
from loguru import logger
from typing import Any, Dict, List, Optional

from .tools.discover import discover_list_schema, get_available_lists
from .tools.ingest import ingest_sharepoint_list
from .tools.search import search_list, search_all_lists
from .tools.manage import source_manager
from .scheduler import schedule_source_sync
from .config import settings


def _build_auth_provider() -> AzureProvider | None:
    if not settings.AUTH_ENABLED:
        logger.info("Auth disabled — running without authentication")
        return None

    if not all([settings.TENANT_ID, settings.CLIENT_ID, settings.CLIENT_SECRET]):
        raise ValueError("AUTH_ENABLED=true requires TENANT_ID, CLIENT_ID, and CLIENT_SECRET")

    provider = AzureProvider(
        client_id=settings.CLIENT_ID,
        client_secret=settings.CLIENT_SECRET,
        tenant_id=settings.TENANT_ID,
        base_url=settings.MCP_BASE_URL,
        identifier_uri=settings.MCP_IDENTIFIER_URI,
        required_scopes=settings.required_scopes_list,
        additional_authorize_scopes=settings.graph_scopes_list,
    )
    logger.info("Auth enabled — AzureProvider configured")
    return provider


_auth_provider = _build_auth_provider()
mcp = FastMCP("SharePoint List Search", auth=_auth_provider)

GRAPH_SEARCH_SCOPES = ["https://graph.microsoft.com/Sites.Read.All"]

# Auth checks: only apply when auth is enabled, otherwise tools are unrestricted
_admin_auth = require_scopes("mcp-admin") if _auth_provider else None
_obo_token_default = EntraOBOToken(GRAPH_SEARCH_SCOPES) if _auth_provider else None


# --- Consumer tools ---

@mcp.tool()
async def get_site_lists_tool(site_url: str) -> Dict[str, Any]:
    """Return all lists available in a SharePoint site with their names, IDs, and metadata."""
    lists = await get_available_lists(site_url)
    return {"site_url": site_url, "lists": lists, "count": len(lists)}


@mcp.tool()
async def discover_list_tool(site_url: str, list_name: str) -> Dict[str, Any]:
    """Inspect a SharePoint list and return its schema with proposed column classification."""
    result = await discover_list_schema(site_url, list_name)
    return result.model_dump()


@mcp.tool()
async def search_tool(
    query: str,
    source: str,
    filters: Optional[str] = None,
    top_k: int = 5,
    graph_token: str = _obo_token_default,
) -> Dict[str, Any]:
    """Semantic search within a single list's index. Pass filters as JSON string, e.g. '{"Status": "Open"}'."""
    import json as _json

    source_config = source_manager.get_source(source)
    if not source_config:
        return {"error": f"Source '{source}' not found. List sources with list_sources tool."}

    parsed_filters = _json.loads(filters) if filters else None
    return await search_list(query, source_config["collection_name"], parsed_filters, top_k, graph_token=graph_token)


@mcp.tool()
async def search_all_tool(
    query: str,
    sources: Optional[List[str]] = None,
    top_k: int = 5,
    graph_token: str = _obo_token_default,
) -> Dict[str, Any]:
    """Semantic search across all registered lists (or a subset)."""
    all_sources = source_manager.list_sources()["sources"]

    if sources:
        target_configs = [s for s in all_sources if s["name"] in sources]
    else:
        target_configs = all_sources

    if not target_configs:
        return {"results": [], "sources_searched": [], "message": "No valid sources found."}

    collection_names = [s["collection_name"] for s in target_configs]
    return await search_all_lists(query, collection_names, top_k, graph_token=graph_token)


@mcp.tool()
async def list_sources_tool() -> Dict[str, Any]:
    """Show all registered searchable lists with their names."""
    data = source_manager.list_sources()
    return {
        "sources": [
            {"name": s["name"], "list_name": s.get("list_name", s["name"])}
            for s in data["sources"]
        ]
    }


# --- Admin tools ---

@mcp.tool(auth=_admin_auth)
async def ingest_list_tool(
    site_url: str,
    list_name: str,
    column_overrides: Optional[Dict[str, str]] = None,
    sync_interval_minutes: int = 60,
) -> Dict[str, Any]:
    """Pull all items from a SharePoint list, embed them, and store in a Zvec collection."""
    try:
        result = await ingest_sharepoint_list(site_url, list_name, column_overrides)
    except Exception as e:
        logger.error(f"Ingest failed: {e}\n{traceback.format_exc()}")
        raise

    source_config = {
        "name": list_name,
        "site_url": site_url,
        "list_name": list_name,
        "collection_name": result["collection_name"],
        "sync_interval_minutes": sync_interval_minutes,
        "column_overrides": column_overrides or {},
        "last_sync": "now",
    }
    source_manager.add_source(source_config)
    await schedule_source_sync(source_config)

    return result


@mcp.tool(auth=_admin_auth)
async def remove_source_tool(source: str) -> str:
    """Remove a registered list, dropping its Zvec collection and config."""
    success = source_manager.remove_source(source)
    if success:
        return f"Source '{source}' removed successfully."
    return f"Source '{source}' not found."


@mcp.tool(auth=_admin_auth)
async def refresh_tool(source: str = None) -> str:
    """Trigger a re-sync of one or all registered lists."""
    if source:
        conf = source_manager.get_source(source)
        if conf:
            await ingest_sharepoint_list(conf["site_url"], conf["list_name"], conf.get("column_overrides"))
            return f"Refreshed source '{source}'"
        return f"Source '{source}' not found"
    else:
        sources = source_manager.list_sources()["sources"]
        for conf in sources:
            await ingest_sharepoint_list(conf["site_url"], conf["list_name"], conf.get("column_overrides"))
        return f"Refreshed {len(sources)} sources."


@mcp.tool(auth=_admin_auth)
async def list_sources_admin_tool() -> Dict[str, Any]:
    """Show all registered lists with full config (admin only)."""
    return source_manager.list_sources()


if __name__ == "__main__":
    if settings.MCP_TRANSPORT == "sse":
        mcp.run(transport="sse", port=settings.MCP_PORT)
    else:
        mcp.run()
