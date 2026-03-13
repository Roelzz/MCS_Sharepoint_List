import traceback

from fastmcp import FastMCP
from loguru import logger
from typing import Any, Dict, List, Optional

from .tools.discover import discover_list_schema, get_available_lists
from .tools.ingest import ingest_sharepoint_list
from .tools.search import search_list, search_all_lists
from .tools.manage import source_manager
from .scheduler import start_scheduler, schedule_source_sync
from .config import settings

# Initialize MCP server
mcp = FastMCP("SharePoint List Search")

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
async def ingest_list_tool(site_url: str, list_name: str, column_overrides: Optional[Dict[str, str]] = None, sync_interval_minutes: int = 60) -> Dict[str, Any]:
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

@mcp.tool()
async def search_tool(query: str, source: str, filters: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
    """Semantic search within a single list's index. Pass filters as JSON string, e.g. '{"Status": "Open"}'."""
    import json as _json
    source_config = source_manager.get_source(source)
    if not source_config:
        return {"error": f"Source '{source}' not found. List sources with list_sources tool."}

    parsed_filters = _json.loads(filters) if filters else None
    return await search_list(query, source_config['collection_name'], parsed_filters, top_k)

@mcp.tool()
async def search_all_tool(query: str, sources: Optional[List[str]] = None, top_k: int = 5) -> Dict[str, Any]:
    """Semantic search across all registered lists (or a subset)."""
    all_sources = source_manager.list_sources()['sources']
    
    if sources:
        target_configs = [s for s in all_sources if s['name'] in sources]
    else:
        target_configs = all_sources
        
    if not target_configs:
        return {"results": [], "sources_searched": [], "message": "No valid sources found."}
        
    collection_names = [s['collection_name'] for s in target_configs]
    return await search_all_lists(query, collection_names, top_k)

@mcp.tool()
async def list_sources_tool() -> Dict[str, Any]:
    """Show all registered lists with their stats."""
    return source_manager.list_sources()

@mcp.tool()
async def remove_source_tool(source: str) -> str:
    """Remove a registered list, dropping its Zvec collection and config."""
    success = source_manager.remove_source(source)
    if success:
        return f"Source '{source}' removed successfully."
    return f"Source '{source}' not found."

@mcp.tool()
async def refresh_tool(source: str = None) -> str:
    """Trigger a re-sync of one or all registered lists."""
    if source:
        conf = source_manager.get_source(source)
        if conf:
            await ingest_sharepoint_list(conf['site_url'], conf['list_name'], conf.get('column_overrides'))
            return f"Refreshed source '{source}'"
        return f"Source '{source}' not found"
    else:
        # Refresh all
        sources = source_manager.list_sources()['sources']
        for conf in sources:
            await ingest_sharepoint_list(conf['site_url'], conf['list_name'], conf.get('column_overrides'))
        return f"Refreshed {len(sources)} sources."

# Start scheduler on server start (FastMCP doesn't have startup hook easily exposed in decorator, 
# but we can run it if we use mcp.run() explicitly or importing module)
# For now, we assume the server runner will handle lifecycle or we rely on lazy init.
# start_scheduler() # Handled separately or needs async context.


if __name__ == "__main__":
    # Run based on config
    if settings.MCP_TRANSPORT == "sse":
        mcp.run(transport="sse", port=settings.MCP_PORT)
    else:
        mcp.run()
