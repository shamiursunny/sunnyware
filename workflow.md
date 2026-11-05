# Sandbox Workflows

## 1. Writing a File (Two Paths)

### A) Keyword Router (Instant)
**User prompt:** "Write a file called demo.csv to sandbox with content 'a,b\n1,2'"
- `keyword_router.py` matches the pattern at the top of `keyword_route()`.
- Returns `{"tool": "write_sandbox_file", "args": {"file": "demo.csv", "content": "a,b\n1,2"}}`.
- The orchestrator executes the tool directly (no LLM).

### B) LLM Tool Call
**User prompt:** "I need to save some data to the sandbox"
- Keyword router does **not** match.
- The LLM is given the tool list and decides to call `write_sandbox_file`.
- The tool runs, writes to `/data/sandbox/demo.csv`.

## 2. Reading a File

**User prompt:** "Read sandbox file demo.csv"
- Keyword router matches → `read_sandbox_file` with `file="demo.csv"`.
- The tool reads from `/data/sandbox` and returns the content.
- The LLM formats the result for the user.

## 3. Previewing a File in the UI
- User clicks a file card in **Library → Sandbox**.
- `openSandboxFileModal(name)` calls `GET /api/sandbox/file/demo.csv`.
- Response is rendered in a modal (text as `<pre>`, images as `<img>`).

## 4. Downloading a File
- Hover over a card → click the download icon.
- `downloadSandboxFile(name)` fetches the content via `GET /api/sandbox/file/…` and triggers a browser download.

## 5. Deleting a File
- Hover over a card → click the trash icon → confirm.
- `DELETE /api/sandbox/file/{name}` removes it from disk.
- UI updates automatically (`sandboxFiles` array is updated).

## 6. Bulk Delete (Select All)
- Click **Select** → **Select All**.
- All cards get checkmarks; toolbar shows **Deselect all** and **Delete (N)**.
- Click **Delete (N)** → confirm → frontend sends `DELETE` for each file to the correct endpoint based on the active tab (`/api/sandbox/file/…` for Sandbox, `/api/library/files/…` for Uploaded, etc.).
- On success, the files are removed from disk and the UI refreshes to show "0 files".

## 7. Missing File Handling
- If the user asks to read a file that doesn't exist, `read_sandbox_file` returns `{"error": "file not found: …"}`.
- The system prompt ensures the LLM responds with **"The file does not exist in the Sandbox"** and **does not** say "please upload it".


---

# Sandbox Workflows (Parts 707-710)

## 1. Writing a File

### A) Keyword Router (Instant)
Prompt: Write a file called demo.csv to sandbox with content a,b
- keyword_route() matches at top
- Returns write_sandbox_file call with file+content
- Executes without LLM

### B) LLM Tool Call
Prompt: I need to save some data to the sandbox
- Router does not match
- LLM calls write_sandbox_file

## 2. Reading a File
Prompt: Read sandbox file demo.csv
- Router matches read_sandbox_file
- Tool reads /data/sandbox/demo.csv
- LLM formats response

## 3. Preview (UI)
Click card -> openSandboxFileModal() -> GET /api/sandbox/file/{name}
- Text shown as <pre>, images as <img>
- Modal has Download / Delete / Close

## 4. Download (UI)
Hover -> download icon -> GET /api/sandbox/file/{name}
- Triggers browser download

## 5. Delete Single File (UI)
Hover -> trash icon -> confirm -> DELETE /api/sandbox/file/{name}

## 6. Bulk Delete (Select All)
Select -> Select All -> Delete (N) -> confirm
- DELETE per file to correct endpoint per tab

## 7. Select All Fix (Part 710)
Root cause: Sandbox/Workspace items had no id.
selected.add(undefined) -> Set deduplicates -> size=1.

Fix in getLibraryItems():
  return items.map(f => f.id ? f : {...f, id: f.name || ''});

## 8. Missing File
LLM says: The file X does not exist in the Sandbox
LLM must NOT say: please upload the file
