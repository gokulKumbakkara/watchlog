from loguru import logger


async def web_search(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        snippets = [r.get("body", "") for r in results if r.get("body")]
        if not snippets:
            return "No results found."
        return "\n\n".join(snippets)
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for query='{query}': {e}")
        return "Search unavailable."
