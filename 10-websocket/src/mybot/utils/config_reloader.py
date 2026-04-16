"""utils/config_reloader.py -- Watchdog-based config file watcher."""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer

from mybot.core.worker import Worker
from mybot.utils.config import Config

logger = logging.getLogger(__name__)


class ConfigHandler(FileSystemEventHandler):
    """Calls config.reload() whenever a watched YAML file changes."""

    def __init__(self, config: Config, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._config = config
        self._loop = loop

    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return
        src = str(event.src_path)
        if src.endswith("config.user.yaml") or src.endswith("config.runtime.yaml"):
            logger.info("Config file changed: %s", src)
            # Schedule reload on the asyncio event loop (thread-safe)
            self._loop.call_soon_threadsafe(self._config.reload)


class ConfigReloader(Worker):
    """Worker that watches workspace for config file changes."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._observer: Observer | None = None

    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        handler = ConfigHandler(config=self._config, loop=loop)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._config.workspace), recursive=False)
        self._observer.start()
        logger.info("ConfigReloader watching %s", self._config.workspace)
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("ConfigReloader stopping")
            self._observer.stop()
            self._observer.join()
            raise
