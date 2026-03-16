import zvec
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import settings

class VectorStore:
    """Wrapper around Zvec collection."""
    
    def __init__(self, collection_name: str, dimension: int = 1536):
        self.collection_name = collection_name
        self.dimension = dimension
        self.path = settings.get_zvec_dir() / collection_name
        
        self.schema = zvec.CollectionSchema(
            name=collection_name,
            vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, dimension),
            fields=[
                zvec.FieldSchema("record_id", zvec.DataType.STRING),
                zvec.FieldSchema("chunk_index", zvec.DataType.INT32),
                zvec.FieldSchema("content", zvec.DataType.STRING),
                zvec.FieldSchema("site_id", zvec.DataType.STRING),
                zvec.FieldSchema("list_id", zvec.DataType.STRING),
                zvec.FieldSchema("list_path", zvec.DataType.STRING),
            ],
        )
        
        # Ensure path exists for persistent storage
        # Zvec create_and_open handles it.

    def _get_collection(self):
        if self.path.exists():
            return zvec.open(path=str(self.path))
        return zvec.create_and_open(path=str(self.path), schema=self.schema)

    def add_documents(self, documents: List[Dict[str, Any]], batch_size: int = 500):
        """
        Add documents to the collection in batches.
        Each doc should have 'id', 'embedding' (list of floats), and metadata fields.
        """
        collection = self._get_collection()

        zvec_docs = []
        for doc in documents:
            vector = doc.pop("embedding")
            doc_id = doc.pop("id")
            zvec_docs.append(zvec.Doc(
                id=doc_id,
                vectors={"embedding": vector},
                fields=doc,
            ))

        for i in range(0, len(zvec_docs), batch_size):
            collection.insert(zvec_docs[i : i + batch_size])

    def search(self, query_vector: List[float], top_k: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        """
        collection = self._get_collection()
        
        # Construct query
        # Filters in Zvec: depends on syntax. 
        # For now, just vector search.
        query = zvec.VectorQuery("embedding", vector=query_vector)
        
        results = collection.query(query, topk=top_k)
        
        # Format results
        formatted = []
        for r in results:
            entry = {
                "id": r.id,
                "score": r.score,
            }
            if r.fields:
                entry["content"] = r.fields.get("content", "")
                entry["metadata"] = {k: v for k, v in r.fields.items() if k != "content"}
            formatted.append(entry)
            
        return formatted

    def delete_collection(self):
        """Delete the entire collection from disk."""
        if self.path.exists():
            shutil.rmtree(self.path)

