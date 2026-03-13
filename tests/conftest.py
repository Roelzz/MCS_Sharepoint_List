import shutil
import tempfile
from pathlib import Path

import pytest

from src.config import settings
from src.tools.discover import discover_list_schema
from src.tools.ingest import ingest_sharepoint_list
from src.tools.manage import source_manager

SITE_URL = "https://copilotstudiotraining-my.sharepoint.com/personal/roel_schenk_copilotstudiotraining_onmicrosoft_com"
LIST_NAME = "vector_search_test_data"


@pytest.fixture(scope="session")
def temp_data_dir():
    tmp = Path(tempfile.mkdtemp(prefix="sp_mcp_test_"))
    original = settings.DATA_DIR
    settings.DATA_DIR = tmp
    yield tmp
    settings.DATA_DIR = original
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
async def ingested_source(temp_data_dir: Path) -> dict:
    result = await ingest_sharepoint_list(SITE_URL, LIST_NAME)

    source_config = {
        "name": LIST_NAME,
        "site_url": SITE_URL,
        "list_name": LIST_NAME,
        "collection_name": result["collection_name"],
        "sync_interval_minutes": 0,
        "column_overrides": {},
        "last_sync": "test",
    }
    source_manager.add_source(source_config)

    yield result

    source_manager.remove_source(LIST_NAME)
