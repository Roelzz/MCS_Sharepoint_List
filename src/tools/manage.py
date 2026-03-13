import json
from pathlib import Path
from typing import List, Dict, Any

from ..config import settings

class SourceManager:
    def __init__(self):
        self.config_path = settings.get_config_dir() / "sources.json"
        
    def _load_sources(self) -> List[Dict[str, Any]]:
        if not self.config_path.exists():
            return []
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                return data.get("sources", [])
        except Exception:
            return []

    def _save_sources(self, sources: List[Dict[str, Any]]):
        with open(self.config_path, "w") as f:
            json.dump({"sources": sources}, f, indent=2)

    def add_source(self, source_config: Dict[str, Any]):
        sources = self._load_sources()
        # Remove existing if same name
        sources = [s for s in sources if s['name'] != source_config['name']]
        sources.append(source_config)
        self._save_sources(sources)

    def list_sources(self) -> Dict[str, Any]:
        return {"sources": self._load_sources()}

    def get_source(self, name: str) -> Dict[str, Any]:
        sources = self._load_sources()
        return next((s for s in sources if s['name'] == name), None)

    def remove_source(self, name: str):
        sources = self._load_sources()
        target = next((s for s in sources if s['name'] == name), None)
        if target:
            # Drop Zvec collection
            from ..store.zvec_store import VectorStore
            store = VectorStore(target['collection_name'])
            store.delete_collection()
            
            # Remove from config
            sources = [s for s in sources if s['name'] != name]
            self._save_sources(sources)
            return True
        return False

source_manager = SourceManager()
