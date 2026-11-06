import httpx
import xml.etree.ElementTree as ET

class ArxivSearchTool:
    name = "arxiv_search"
    description = "Search arXiv for academic papers and preprints (free, no API key)."
    keywords = ["arxiv", "academic papers", "research papers", "preprints"]
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (e.g., 'quantum computing')"},
            "max_results": {"type": "integer", "description": "Max results (default: 5)", "default": 5}
        },
        "required": ["query"]
    }

    async def run(self, query: str, max_results: int = 5) -> dict:
        url = f"https://export.arxiv.org/api/query?search_query=all:{query}&max_results={max_results}"
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"error": f"arXiv API error: {resp.status_code}"}
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            results = []
            for entry in entries:
                title = entry.find("atom:title", ns)
                summary = entry.find("atom:summary", ns)
                link = entry.find("atom:id", ns)
                results.append({
                    "title": title.text.strip() if title is not None else "",
                    "summary": (summary.text.strip()[:300] + "...") if summary is not None else "",
                    "url": link.text.strip() if link is not None else ""
                })
            return {"ok": True, "count": len(results), "results": results}
