"""
commands/web_commands.py — Web search and URL opening.
"""

import urllib.parse
import webbrowser

from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)


@register_command("web_search")
def web_search(query: str) -> str:
    """Open the default browser with a Google search for *query*."""
    if not query:
        return "What would you like me to search for?"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    webbrowser.open(url)
    log.info("Web search: %s", query)
    return f"Searching the web for: {query}"


@register_command("open_url")
def open_url(url: str) -> str:
    """Open an arbitrary URL in the default browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    log.info("Opened URL: %s", url)
    return f"Opening {url} in your browser."

@register_command("show_news")
def show_news(_: str) -> str:
    url = "https://www.worldmonitor.app/?lat=27.9708&lon=75.6030&zoom=4.85&view=global&timeRange=all&layers=conflicts%2Cbases%2Chotspots%2Cnuclear%2Csanctions%2Cweather%2Ceconomic%2Cwaterways%2Coutages%2Cmilitary%2Cnatural%2Cspaceports%2CiranAttacks"
    webbrowser.open(url)
    return "Opening World Monitor news, sir."