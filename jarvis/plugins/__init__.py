"""
plugins/__init__.py — Lightweight plugin loader.

Drop any Python file into the plugins/ directory that calls
@register_command(...) at import time, and it will be auto-loaded
by PluginLoader.load_all().

Example plugin file (plugins/weather_plugin.py):

    from commands import register_command
    import requests

    @register_command("weather")
    def get_weather(city: str) -> str:
        ...
"""

import importlib
import importlib.util
import sys
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)


class PluginLoader:
    def __init__(self, plugin_dir: Path) -> None:
        self._dir = plugin_dir

    def load_all(self) -> int:
        """
        Import all *.py files in the plugin directory (except __init__).
        Returns the number of successfully loaded plugins.
        """
        if not self._dir.exists():
            log.debug("Plugin directory not found: %s", self._dir)
            return 0

        loaded = 0
        for path in sorted(self._dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            module_name = f"plugins.{path.stem}"
            try:
                if module_name in sys.modules:
                    continue   # Already loaded
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    loaded += 1
                    log.info("Loaded plugin: %s", path.name)
            except Exception as exc:
                log.error("Failed to load plugin '%s': %s", path.name, exc)

        return loaded
