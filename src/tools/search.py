import asyncio
from typing import List, Dict, Any, Optional
from ..pipeline.embedder import Embedder
from ..store.zvec_store import VectorStore

embedder = Embedder()

async def search_list(query: str, collection_name: str, filters: Dict[str, Any] = None, top_k: int = 5) -> Dict[str, Any]:
    """
    Search a single list (collection).
    1. Embed query
    2. Vector Search
    3. Format
    """
    # 1. Embed
    query_vector = (await embedder.embed_texts([query]))[0]
    
    # 2. Search
    store = VectorStore(collection_name)
    results = store.search(query_vector, top_k=top_k * 2, filters=filters) # Fetch more for deduplication
    
    # 3. Deduplicate by record_id
    seen_records = set()
    unique_results = []
    
    for r in results:
        # Assuming result has metadata properties
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
        "total_candidates": len(results), # Mock total
        "query": query
    }

async def search_all_lists(query: str, sources: List[str], top_k: int = 5) -> Dict[str, Any]:
    """
    Search across multiple lists.
    """
    tasks = [search_list(query, source, top_k=top_k) for source in sources]
    results_list = await asyncio.gather(*tasks)
    
    # Flatten and sort by score
    all_results = []
    for res in results_list:
        for item in res['results']:
            item['source'] = res['source']
            all_results.append(item)
            
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        "results": all_results[:top_k],
        "sources_searched": sources
    }
