import time
from typing import List, Dict, Any

from ..sharepoint.client import sharepoint_client
from ..store.zvec_store import VectorStore
from ..tools.discover import discover_list_schema, DiscoveryResult, ColumnInfo
from ..pipeline.chunker import Chunker
from ..pipeline.embedder import Embedder

# Fix circular imports and instantiation
chunker = Chunker()
embedder = Embedder()

async def ingest_sharepoint_list(site_url: str, list_name: str, column_overrides: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Full ingest pipeline:
    1. Discover Schema
    2. Fetch Items
    3. Template & Chunk
    4. Embed
    5. Store
    """
    start_time = time.time()
    
    # 1. Discover Schema
    schema = await discover_list_schema(site_url, list_name)
    list_id = schema.list_id
    
    # Apply overrides
    if column_overrides:
        for col in schema.columns:
            if col.internal_name in column_overrides:
                col.classification = column_overrides[col.internal_name]
                
    # 2. Setup Store
    collection_name = f"src_{list_name.replace(' ', '_')}_{list_id[:8]}"
    store = VectorStore(collection_name)
    
    # 3. Fetch Items
    site_id = await sharepoint_client.get_site_id_by_url(site_url)
    items = await sharepoint_client.get_list_items(site_id, list_id)

    # Derive list_path for security trimming (SharePoint convention)
    list_path = f"{site_url.rstrip('/')}/Lists/{list_name}"
    
    # 4. Process Items
    embed_fields = [c for c in schema.columns if c.classification == 'embed']
    filter_fields = [c for c in schema.columns if c.classification == 'filter']
    chunk_fields = [c for c in schema.columns if c.classification == 'chunk']

    documents = []
    texts_to_embed = []

    for item in items:
        fields = item.fields.additional_data if item.fields else {}
        item_id = item.id

        # Metadata prefix
        metadata_parts = []
        for col in embed_fields + filter_fields:
            val = fields.get(col.internal_name)
            if val:
                metadata_parts.append(f"{col.display_name}: {val}")
        metadata_prefix = ". ".join(metadata_parts)

        # Chunk text
        chunks = []
        if chunk_fields:
            chunk_text = ""
            for col in chunk_fields:
                val = fields.get(col.internal_name)
                if val:
                    chunk_text += f"{col.display_name}:\n{val}\n\n"

            chunks = chunker.chunk_text(chunk_text, metadata_prefix)
        else:
            chunks = [metadata_prefix]

        # Prepare docs
        for i, chunk in enumerate(chunks):
            doc_id = f"{item_id}_{i}"
            documents.append({
                "id": doc_id,
                "record_id": item_id,
                "chunk_index": i,
                "content": chunk,
                "site_id": site_id,
                "list_id": list_id,
                "list_path": list_path,
            })
            texts_to_embed.append(chunk)

    # 5. Embed (Batching needed for production)
    vectors = await embedder.embed_texts(texts_to_embed)
    
    # Attach vectors
    for doc, vec in zip(documents, vectors):
        doc["embedding"] = vec
        
    # 6. Store
    store.add_documents(documents)
    
    return {
        "source_name": list_name,
        "collection_name": collection_name,
        "records_processed": len(items),
        "chunks_created": len(documents),
        "duration_seconds": int(time.time() - start_time),
        "status": "complete"
    }
