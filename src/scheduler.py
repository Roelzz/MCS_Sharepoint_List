import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from typing import Dict, Any

from .tools.ingest import ingest_sharepoint_list
from .tools.manage import source_manager

DEFAULT_SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))

scheduler = AsyncIOScheduler()

async def sync_job(source_config: Dict[str, Any]):
    try:
        await ingest_sharepoint_list(
            site_url=source_config['site_url'],
            list_name=source_config['list_name'],
            column_overrides=source_config.get('column_overrides')
        )
        logger.info(f"Sync completed for {source_config['name']}")
    except Exception as e:
        logger.error(f"Sync failed for {source_config['name']}: {e}")


def start_scheduler():
    scheduler.start()
    
    # Load sources and schedule jobs
    sources = source_manager.list_sources()['sources']
    for source in sources:
        interval = source.get('sync_interval_minutes', DEFAULT_SYNC_INTERVAL)
        if interval > 0:
            scheduler.add_job(
                sync_job,
                IntervalTrigger(minutes=interval),
                args=[source],
                id=f"sync_{source['name']}",
                replace_existing=True
            )
            
async def schedule_source_sync(source_config: Dict[str, Any]):
    interval = source_config.get('sync_interval_minutes', DEFAULT_SYNC_INTERVAL)
    if interval > 0:
        scheduler.add_job(
            sync_job,
            IntervalTrigger(minutes=interval),
            args=[source_config],
            id=f"sync_{source_config['name']}",
            replace_existing=True
        )
