import asyncio
import logging

from src.config import settings
from src.orchestrator import poll_active_sessions, scan_and_dispatch

logger = logging.getLogger(__name__)


async def polling_loop() -> None:
    """Background task that polls Devin sessions for status updates."""
    logger.info(f"Poller started (interval={settings.poll_interval}s)")
    while True:
        try:
            await poll_active_sessions()
        except Exception as e:
            logger.error(f"Polling error: {e}")
        await asyncio.sleep(settings.poll_interval)


async def scan_loop() -> None:
    """Background task that periodically scans for new issues."""
    if settings.scan_interval_minutes <= 0:
        logger.info("Periodic scan disabled (SCAN_INTERVAL_MINUTES=0)")
        return

    interval = settings.scan_interval_minutes * 60
    logger.info(f"Scanner started (interval={settings.scan_interval_minutes}min)")
    while True:
        await asyncio.sleep(interval)
        try:
            await scan_and_dispatch()
        except Exception as e:
            logger.error(f"Scan error: {e}")
