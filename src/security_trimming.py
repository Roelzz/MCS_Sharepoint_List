import asyncio
from typing import Dict, List, Optional, Set

import httpx
from loguru import logger


_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def filter_by_permissions(
    candidates: List[Dict],
    graph_token: Optional[str],
    batch_size: int = 50,
) -> List[Dict]:
    """Filter search results to only items the user has access to via SharePoint Search API.

    Uses the SharePoint Search REST API with the user's delegated token.
    The Search API only returns results the caller has permission to see (security trimming).

    Args:
        candidates: Search results with metadata containing list_path and record_id.
        graph_token: Delegated Graph API token (OBO). If None, returns all candidates (no trimming).
        batch_size: Max items per Search API request.

    Returns:
        Filtered list of candidates the user can access.
    """
    if not graph_token:
        logger.debug("No graph token — skipping security trimming")
        return candidates

    items_by_list = _group_by_list(candidates)
    if not items_by_list:
        return candidates

    accessible_ids: Set[str] = set()
    tasks = []
    for list_path, item_ids in items_by_list.items():
        for i in range(0, len(item_ids), batch_size):
            batch = item_ids[i : i + batch_size]
            tasks.append(_check_batch(graph_token, list_path, batch))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"Security trimming batch failed: {result}")
            continue
        accessible_ids.update(result)

    trimmed = [c for c in candidates if _candidate_id(c) in accessible_ids]
    logger.info(f"Security trimming: {len(candidates)} candidates -> {len(trimmed)} accessible")
    return trimmed


def _group_by_list(candidates: List[Dict]) -> Dict[str, List[str]]:
    """Group candidates by list_path, extracting record_ids."""
    groups: Dict[str, List[str]] = {}
    for c in candidates:
        metadata = c.get("metadata", {})
        list_path = metadata.get("list_path")
        record_id = metadata.get("record_id") or c.get("id", "").split("_")[0]
        if not list_path:
            continue
        groups.setdefault(list_path, []).append(record_id)
    return groups


def _candidate_id(candidate: Dict) -> str:
    """Extract a unique ID for matching against accessible items."""
    metadata = candidate.get("metadata", {})
    return metadata.get("record_id") or candidate.get("id", "").split("_")[0]


async def _check_batch(
    graph_token: str,
    list_path: str,
    item_ids: List[str],
) -> Set[str]:
    """Check which items in a batch the user can access via SharePoint Search API.

    Constructs a KQL query targeting specific ListItemIDs within a list path.
    The Search API automatically trims results to only those the user can see.
    """
    id_filter = " OR ".join(f"ListItemID:{item_id}" for item_id in item_ids)
    kql = f"path:\"{list_path}\" AND ({id_filter})"

    payload = {
        "requests": [
            {
                "entityTypes": ["listItem"],
                "query": {"queryString": kql},
                "from": 0,
                "size": len(item_ids),
                "fields": ["ListItemID"],
            }
        ]
    }

    client = _get_http_client()
    headers = {
        "Authorization": f"Bearer {graph_token}",
        "Content-Type": "application/json",
    }

    try:
        resp = await client.post(
            "https://graph.microsoft.com/v1.0/search/query",
            json=payload,
            headers=headers,
        )

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning(f"Graph Search 429 — retrying after {retry_after}s")
            await asyncio.sleep(retry_after)
            resp = await client.post(
                "https://graph.microsoft.com/v1.0/search/query",
                json=payload,
                headers=headers,
            )

        resp.raise_for_status()
        data = resp.json()

        accessible: Set[str] = set()
        for result_set in data.get("value", []):
            for hit_container in result_set.get("hitsContainers", []):
                for hit in hit_container.get("hits", []):
                    resource = hit.get("resource", {})
                    properties = resource.get("properties", {})
                    list_item_id = properties.get("ListItemID") or properties.get("listItemId")
                    if list_item_id:
                        accessible.add(str(list_item_id))

        return accessible

    except httpx.HTTPStatusError as e:
        logger.error(f"Graph Search API error: {e.response.status_code} — {e.response.text[:200]}")
        raise
    except Exception as e:
        logger.error(f"Security trimming request failed: {e}")
        raise
