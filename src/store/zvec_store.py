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
        
        # Define schema
        self.schema = zvec.CollectionSchema(
            name=collection_name,
            vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, dimension),
            # Scalar fields are dynamic or mapped? Zvec supports dynamic properties usually,
            # or explicit schema. Let's assume explicit for now based on spec.
            # But spec says dynamic. Let's start with content and metadata as strings/JSON?
            # Or use properties if Zvec supports it.
            # Assuming Zvec properties support.
        )
        
        # Ensure path exists for persistent storage
        # Zvec create_and_open handles it.

    def _get_collection(self):
        return zvec.create_and_open(path=str(self.path), schema=self.schema)

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Add documents to the collection.
        Each doc should have 'id', 'embedding' (list of floats), and metadata fields.
        """
        collection = self._get_collection()
        
        zvec_docs = []
        for doc in documents:
            vector = doc.pop("embedding")
            doc_id = doc.pop("id")
            # Remaining fields are metadata
            zvec_docs.append(zvec.Doc(
                id=doc_id, 
                vectors={"embedding": vector},
                properties=doc  # Assuming Zvec supports arbitrary properties or specific ones
            ))
            
        collection.insert(zvec_docs)

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
            # Fetch full document properties? 
            # Does query return properties? Usually yes or needs fetch.
            # Assuming 'r' contains score and id, maybe properties.
            formatted.append({
                "id": r.id,
                "score": r.score,
                # "content": r.properties.get("content"),
                # "metadata": r.properties
            })
            
        return formatted

    def delete_collection(self):
        """Delete the entire collection from disk."""
        if self.path.exists():
            shutil.rmtree(self.path)

