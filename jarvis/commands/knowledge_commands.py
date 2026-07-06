"""
commands/knowledge_commands.py — Wikipedia lookups and knowledge queries.
"""

from commands import register_command
from utils.logger import get_logger

log = get_logger(__name__)

try:
    import wikipedia
    _WIKI_AVAILABLE = True
except ImportError:
    _WIKI_AVAILABLE = False
    log.warning("'wikipedia' package not installed. Wiki commands degraded.")


@register_command("wikipedia")
def wiki_search(query: str) -> str:
    """
    Fetch a short Wikipedia summary for *query*.
    Falls back to a browser search if the package is unavailable.
    """
    if not query:
        return "What would you like to know about?"

    if not _WIKI_AVAILABLE:
        import webbrowser, urllib.parse
        url = f"https://en.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return f"Opening Wikipedia search for {query}."

    try:
        # wikipedia.summary raises DisambiguationError or PageError on failure
        summary = wikipedia.summary(query, sentences=3, auto_suggest=True)
        log.info("Wikipedia query: %s", query)
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        options = ", ".join(e.options[:3])
        return f"That's ambiguous. Did you mean: {options}?"
    except wikipedia.exceptions.PageError:
        return f"I couldn't find a Wikipedia page for '{query}'."
    except Exception as exc:
        log.error("Wikipedia error: %s", exc)
        return "I had trouble reaching Wikipedia. Please try again."


@register_command("define")
def define_word(word: str) -> str:
    """Return a short Wikipedia-based definition."""
    return wiki_search(word)
