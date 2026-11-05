# Sandbox Integration (Parts 707–710)

## Overview
The **Sandbox** is a persistent directory (`/data/sandbox`) where the AI can write intermediate files (CSVs, database dumps, cleaned data) that appear in the **Library → Sandbox** tab. Users can preview, download, delete individual files, or bulk-delete via select mode.

## What Was Added

### Tools (`src/sunnyware/tools/`)
- **`write_sandbox_file`** – writes a file to `/data/sandbox` (`category = "Sandbox"`).
- **`read_sandbox_file`** – reads a file back from `/data/sandbox` (`category = "Sandbox"`).

Both tools are **registered** in `tools/__init__.py` and exposed in the Tools dropdown under the **Sandbox** category (first, at the top).

### Keyword Router (`src/sunnyware/keyword_router.py`)
Sandbox intent detection is placed at the **very start** of `keyword_route()` — before any generic "write file" / "read file" logic — so these prompts are handled instantly without LLM routing:

| Pattern | Tool | Example |
|---------|------|---------|
| `write/save/create a file called X to sandbox` | `write_sandbox_file` | *"Write a file called demo.csv to sandbox with content 'a,b'"* |
| `read/show/get X from sandbox` | `read_sandbox_file` | *"Read sandbox file demo.csv"* |
| `show me X in sandbox` | `read_sandbox_file` | *"Show me demo.csv in sandbox"* |

### API Endpoints (Backend — `src/sunnyware/routes/library.py`)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/sandbox/files` | List all files in the sandbox |
| `GET` | `/api/sandbox/file/{name}` | Get file content (text or base64 for images) |
| `DELETE` | `/api/sandbox/file/{name}` | Delete a single file from disk |
| `POST` | `/api/sandbox/clear` | Delete all files (button removed from UI; still callable via API) |

All endpoints use `paths.sandbox()` which falls back to `./data/sandbox` or `/tmp/sandbox` if `/data` is not writable.

### Frontend (`static/chat.html`)
- **Preview modal** — clicking a sandbox card opens a modal with file content (text as `<pre>`, images as `<img>`).
- **Hover actions** — download and delete icons appear on each file card.
- **Download** — fetches via `GET /api/sandbox/file/{name}` and triggers browser download.
- **Delete** — calls `DELETE /api/sandbox/file/{name}` and removes the card.
- **Select All / Deselect All** — correct counts and toggle behavior on **all four tabs** (Uploaded, Workspace, Sandbox, AI Generated).
- **Bulk delete** — routes DELETE to the correct endpoint based on the active tab.
- **Clear Sandbox button** — removed (redundant with Select All → Delete).

### System Prompt (`src/sunnyware/prompts.py`)
- Explicitly instructs the LLM to call `write_sandbox_file` as a **separate tool**, not from inside `python_eval`.
- Provides concrete examples:
  - `write_sandbox_file(file='demo.csv', content='a,b\n1,2')`
  - `read_sandbox_file(file='demo.csv')`
- Tells the LLM to **never** say "please upload the file" when a sandbox file is missing; it must state the file doesn't exist.

### Orchestrator & Jarvis
- `orchestrator.py` — added tool aliases: `sandbox → write_sandbox_file`, `read_sandbox → read_sandbox_file`, `readsandbox → read_sandbox_file`.
- `jarvis_agent.py` — added `sandbox`, `save to sandbox`, `read sandbox` to `tool_keywords`.
- `routes/meta.py` — `/api/tools` respects explicit `category` from tool class, and custom category ordering puts **"Sandbox"** first.

## Final State

| Area | Status |
|------|--------|
| Keyword Router (instant, no LLM) | ✅ Write / Read / Show / Save |
| Jarvis / Orchestrator (LLM tool calling) | ✅ |
| Embedded model | ✅ |
| Slash bots | ✅ |
| UI dropdown "Sandbox" category (top) | ✅ |
| Preview modal, hover download, hover delete | ✅ |
| Select All / Deselect All across all 4 tabs | ✅ Fixed |
| Bulk delete routing per tab | ✅ Fixed |
| Backend file deletion from disk | ✅ Verified |
| Missing-file graceful error | ✅ |

## Known Limitations
- Sandbox files are **ephemeral** on HF Spaces unless a persistent bucket is mounted; they are wiped on restart.
- Workspace and AI Generated tabs have **no backend delete endpoint**; deletions are frontend-only.
- `POST /api/sandbox/clear` exists but has no UI button.
- `read_sandbox_file` returns text only for non-image files; binary formats are base64-encoded.

## Next Steps (Future Work)
- Auto-cleanup of files older than 7 days on startup.
- "Download All as ZIP" button in the Sandbox tab.
- Preview modal for Workspace / AI Generated files.


## Full-Screen File Viewer (Parts 711-712)

The Sandbox tab - and every other Library tab - opens files in a universal full-screen viewer.

### Viewer Features
- Click any file card -> full-screen overlay with X/N/M navigation
- File-type rendering: CSV=table, JSON=pretty, Image=centered, PDF=iframe, XLSX=table, Binary=friendly message

### New Endpoints (Parts 711-712)
- GET /api/workspace/file/{name} - workspace file reader
- GET /api/sandbox/download-zip - stream all sandbox files as ZIP
- GET /api/sandbox/file/{name}/xlsx - parse xlsx in sandbox

### ZIP Download
- Download ZIP button visible only on Sandbox tab (hidden in select mode)
- Downloads sandbox-YYYY-MM-DD.zip

### Binary Guard
Returns type:binary for .xlsx/.xls/.docx/.doc/.pptx/.ppt/.zip/.gz/.tar - except .xlsx in sandbox which routes to /xlsx endpoint (parses to tables).


## Office Preview (Part 713)

The full-screen viewer now supports Office documents and BI files.

### Supported Formats
- .docx -> paragraphs + tables (fallback to raw text for invalid packages)
- .pptx -> slide list (fallback to raw text for invalid packages)
- .twb/.twbx -> Tableau structure
- .pbix -> Power BI metadata

### Looker Studio
No offline file format - cloud only. PDF exports work via existing PDF viewer.

### New Endpoints
- GET /api/workspace/file/{name}/office-preview
- GET /api/sandbox/file/{name}/office-preview

### Sandbox Integration
- docx and pptx added to ALLOWED_MODULES whitelist
- Fixed UnboundLocalError in sandbox_import
- python_eval can now create real .docx files via sandbox_path()

### Image Zoom Controls
Header shows - 100% + 1:1 for image files.

### Jump Dropdown
Header select allows jumping directly to any file in current tab.


## Legacy Office (Part 714)

### Supported Legacy Formats
- .doc (Word 97-2003) -> LibreOffice conversion -> paragraphs + tables
  - Fallback: antiword (text-only) if LibreOffice fails
- .ppt (PowerPoint 97-2003) -> LibreOffice conversion -> slide cards
  - Fallback: catppt (text-only) if LibreOffice fails

### System Packages (packages.txt)
- libreoffice-writer - .doc -> .docx conversion
- libreoffice-impress - .ppt -> .pptx conversion
- antiword - .doc text fallback
- catdoc - .doc + .ppt text fallback (provides catppt)

### API Endpoints
Reuses /api/{workspace|sandbox}/file/{name}/office-preview - the dispatcher routes by extension:
- .doc -> parse_doc()
- .ppt -> parse_ppt()

### Deployment
Requires Factory rebuild (not Restart) to install the ~350MB of packages. After build, LibreOffice is baked into the Docker image - future restarts are instant.

### Fallback Behavior
- LibreOffice is tried first - provides full formatting (headings, tables, lists)
- If LO fails (binary corruption, incompatible format) -> antiword/catppt (text-only with warning banner)
- If both fail -> clean error message to user
