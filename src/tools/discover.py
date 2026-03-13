import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from ..sharepoint.client import sharepoint_client

class ColumnInfo(BaseModel):
    internal_name: str
    display_name: str
    type: str
    classification: str = Field(..., description="Proposed classification: embed, filter, chunk, retrieve, skip")
    sample_values: Optional[List[str]] = None
    avg_tokens: Optional[int] = None

class DiscoveryResult(BaseModel):
    list_id: str
    list_name: str
    item_count: int
    columns: List[ColumnInfo]
    estimated_chunks: int
    estimated_ingest_time_seconds: int

async def discover_list_schema(site_url: str, list_name: str) -> DiscoveryResult:
    """
    Inspect a SharePoint list and return its schema with proposed column classification.
    """
    # 1. Resolve site ID
    site_id = await sharepoint_client.get_site_id_by_url(site_url)
    
    # 2. Get list ID (need implementation to find list by name in site lists)
    # Mocking list discovery for now or assume list_name IS list_id if GUID
    lists = await sharepoint_client.get_site_lists(site_id)
    target_list = next(
        (l for l in lists if l.display_name == list_name or l.id == list_name),
        None,
    )

    if not target_list:
        raise ValueError(f"List '{list_name}' not found in site '{site_url}'")

    list_id = target_list.id
    item_count = await sharepoint_client.get_list_item_count(site_id, list_id)

    # 3. Get columns
    columns = await sharepoint_client.get_list_columns(site_id, list_id)

    # 4. Filter and classify
    classified_columns = []
    for col in columns:
        if getattr(col, 'read_only', False) or getattr(col, 'hidden', False):
            continue

        c_type = "text"
        if col.text is not None:
            c_type = "text"
        elif col.number is not None:
            c_type = "number"
        elif col.date_time is not None:
            c_type = "datetime"
        elif col.choice is not None:
            c_type = "choice"
        elif col.person_or_group is not None:
            c_type = "person"
        elif col.lookup is not None:
            c_type = "lookup"
        elif col.boolean is not None:
            c_type = "boolean"

        # Simple heuristic classification
        classification = "embed"
        if c_type in ['choice', 'boolean', 'number', 'datetime', 'person', 'lookup']:
            classification = "filter"
        elif c_type == 'note':
            classification = "chunk"

        classified_columns.append(ColumnInfo(
            internal_name=col.name,
            display_name=col.display_name,
            type=c_type,
            classification=classification
        ))

    # 5. Estimate chunks (very rough)
    est_chunks = item_count  # 1 chunk per item minimum
    # If chunks classified, add multiplier
    if any(c.classification == 'chunk' for c in classified_columns):
        est_chunks *= 3 # simple heuristic
        
    return DiscoveryResult(
        list_id=list_id,
        list_name=target_list.display_name,
        item_count=item_count,
        columns=classified_columns,
        estimated_chunks=est_chunks,
        estimated_ingest_time_seconds=int(est_chunks * 0.5) # 0.5s per chunk ingest
    )
