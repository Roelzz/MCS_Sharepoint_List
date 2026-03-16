import asyncio
from typing import Dict, Any, List, Optional

from loguru import logger

from ..pipeline.embedder import Embedder
from ..store.zvec_store import VectorStore
from ..security_trimming import filter_by_permissions

embedder = Embedder()


async def search_list(
    query: str,
    collection_name: str,
    filters: Dict[str, Any] = None,
    top_k: int = 5,
    graph_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Search a single list with optional security trimming."""
    query_vector = (await embedder.embed_texts([query]))[0]

    store = VectorStore(collection_name)
    # Fetch extra candidates for dedup + security trimming overhead
    fetch_multiplier = 4 if graph_token else 2
    results = store.search(query_vector, top_k=top_k * fetch_multiplier, filters=filters)

    # Security trim before dedup (removes items user can't access)
    if graph_token:
        has_list_path = any(r.get("metadata", {}).get("list_path") for r in results)
        if has_list_path:
            results = await filter_by_permissions(results, graph_token)
        else:
            logger.warning(f"Collection {collection_name} missing list_path metadata — skipping security trimming (re-ingest required)")

    # Deduplicate by record_id
    seen_records: set[str] = set()
    unique_results: list[Dict] = []

    for r in results:
        record_id = r.get("metadata", {}).get("record_id") or r["id"].split("_")[0]
        if record_id in seen_records:
            continue
        seen_records.add(record_id)
        unique_results.append(r)
        if len(unique_results) >= top_k:
            break

    return {
        "source": collection_name,
        "results": unique_results,
        "total_candidates": len(results),
        "query": query,
    }


async def search_all_lists(
    query: str,
    sources: List[str],
    top_k: int = 5,
    graph_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Search across multiple lists with security trimming."""
    tasks = [search_list(query, source, top_k=top_k, graph_token=graph_token) for source in sources]
    results_list = await asyncio.gather(*tasks)

    all_results: list[Dict] = []
    for res in results_list:
        for item in res["results"]:
            item["source"] = res["source"]
            all_results.append(item)

    all_results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "results": all_results[:top_k],
        "sources_searched": sources,
    }
