import httpx

class DomainResearchTool:
    name = "domain_research"
    description = "Search free research papers across finance, investment, insurance, and legal domains."
    keywords = ["domain research", "finance papers", "investment papers", "insurance papers", "legal papers"]
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (e.g., 'value investing', 'IFRS 17')"},
            "domain": {"type": "string", "description": "finance, investment, insurance, or legal"},
            "max_results": {"type": "integer", "description": "Max results (default: 5)", "default": 5}
        },
        "required": ["query", "domain"]
    }

    async def run(self, query: str, domain: str, max_results: int = 5) -> dict:
        domain = domain.lower()
        if domain not in ("finance", "investment", "insurance", "legal"):
            return {"error": f"Unsupported domain '{domain}'. Choose from: finance, investment, insurance, legal."}

        results = []
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            # 1. OpenAlex (always)
            openalex_url = f"https://api.openalex.org/works?search={query}&per-page={max_results}"
            try:
                resp = await client.get(openalex_url)
                if resp.status_code == 200:
                    data = resp.json()
                    for work in data.get("results", []):
                        results.append({
                            "source": "OpenAlex",
                            "title": (work.get("title") or "")[:120],
                            "url": work.get("doi") or work.get("primary_location", {}).get("landing_page_url", "#")
                        })
            except Exception:
                pass

            # 2. Domain-specific source
            if domain in ("finance", "investment", "insurance"):
                arxiv_url = f"https://export.arxiv.org/api/query?search_query=all:{query}+AND+cat:q-fin.*&max_results={max_results}"
                try:
                    resp = await client.get(arxiv_url)
                    if resp.status_code == 200:
                        import defusedxml.ElementTree as ET
                        root = ET.fromstring(resp.text)
                        ns = {"atom": "http://www.w3.org/2005/Atom"}
                        for entry in root.findall("atom:entry", ns):
                            title = entry.find("atom:title", ns)
                            link = entry.find("atom:id", ns)
                            results.append({
                                "source": "arXiv (q-fin)",
                                "title": (title.text.strip()[:120] if title is not None else ""),
                                "url": link.text.strip() if link is not None else "#"
                            })
                except Exception:
                    pass
            elif domain == "legal":
                doaj_url = f"https://doaj.org/api/search/articles/{query}?pageSize={max_results}"
                try:
                    resp = await client.get(doaj_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", []):
                            bibjson = item.get("bibjson", {})
                            results.append({
                                "source": "DOAJ",
                                "title": (bibjson.get("title") or "")[:120],
                                "url": bibjson.get("link", [{}])[0].get("url", "#") if bibjson.get("link") else "#"
                            })
                except Exception:
                    pass

        if not results:
            return {"error": f"No results found for '{query}' in domain '{domain}'."}

        return {
            "ok": True,
            "query": query,
            "domain": domain,
            "count": len(results),
            "results": results[:max_results]
        }
