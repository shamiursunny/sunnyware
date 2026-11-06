from pathlib import Path
from .. import paths

class ScrapeWebpageTool:
    name = "scrape_webpage"
    description = "Scrape tables from a webpage URL and save them as a CSV file."
    keywords = ["scrape web", "scrape url", "extract table from website"]
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL of the webpage to scrape"},
            "table_index": {"type": "integer", "description": "Which table on the page to extract (0-indexed, default 0)"},
            "output_filename": {"type": "string", "description": "Name of the CSV file to save"}
        },
        "required": ["url", "output_filename"]
    }

    async def run(self, url: str, output_filename: str = None, table_index: int = 0, kind: str = "sandbox") -> dict:
        import pandas as pd
        import requests
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Extract tables using pandas
            try:
                tables = pd.read_html(response.text)
            except ValueError as e:
                if "No tables found" in str(e):
                    return {"error": "No HTML tables found on this page. The site likely uses a JavaScript framework (like React/Vue). Try 'extract all links' or 'screenshot' instead."}
                raise e

            if not tables:
                return {"error": "No tables found on the page"}
            if table_index >= len(tables):
                return {"error": f"Table index {table_index} out of range. Found {len(tables)} tables."}

            df = tables[table_index]
            out_path = paths.sandbox() / Path(output_filename).name
            df.to_csv(out_path, index=False)
            
            return {
                "ok": True,
                "message": f"Successfully scraped table {table_index} and saved to {out_path.name}",
                "rows": len(df),
                "columns": list(df.columns)
            }
        except Exception as e:
            return {"error": f"Scraping failed: {str(e)}"}

class GenerateReportTool:
    name = "generate_report"
    description = "Generate a formatted HTML report from a CSV/Excel dataset, including a summary table and a chart."
    keywords = ["generate report", "create html report", "data report"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The CSV or Excel file to report on"},
            "title": {"type": "string", "description": "Title of the report"},
            "output_filename": {"type": "string", "description": "Name of the HTML file to save"}
        },
        "required": ["filename", "title", "output_filename"]
    }

    async def run(self, filename: str, title: str, output_filename: str, kind: str = "sandbox") -> dict:
        import pandas as pd
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists():
            return {"error": f"File {filename} not found"}

        try:
            if target.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(target)
            else:
                df = pd.read_csv(target)
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}

        # Generate a quick summary
        summary = df.describe(include='all').to_html(classes='table table-striped', border=0)
        raw_html = df.head(50).to_html(classes='table table-striped', border=0)

        html_content = f"""
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <p><strong>Source File:</strong> {filename}</p>
            <p><strong>Total Rows:</strong> {len(df)}</p>
            
            <h2>Data Summary</h2>
            {summary}
            
            <h2>Data Preview (First 50 rows)</h2>
            {raw_html}
        </body>
        </html>
        """

        out_path = paths.sandbox() / Path(output_filename).name
        out_path.write_text(html_content, encoding="utf-8")

        return {
            "ok": True,
            "message": f"Report saved to sandbox as {out_path.name}",
            "file": out_path.name
        }
