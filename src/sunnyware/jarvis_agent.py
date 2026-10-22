# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""
Local Jarvis Agent for token-efficient tool calling.
Uses sentence-transformers for tool retrieval and llama-cpp-python for local tool selection.
"""

import json
from .agent_memory import write_memory
import os
import asyncio
import re
from typing import List, Dict, Any, Optional
from . import local_llm_s3 as local_llm

# Part 307: Simplify array types to strings for the local model
def _simplify_schema(params):
    if not params:
        return {}
    new_params = {}
    for k, v in params.items():
        new_v = dict(v)
        if new_v.get("type") == "array":
            new_v["type"] = "string"
            new_v["description"] = new_v.get("description", "") + " (comma-separated list of values)"
        new_params[k] = new_v
    return new_params
from .tools import _TOOLS, get_tool, list_tools

# Lazy load embedding model
_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            import os
            from sentence_transformers import SentenceTransformer
            print("[jarvis] Loading embedding model...", flush=True)
            
            cache_dir = "/data/hub"
            os.makedirs(cache_dir, exist_ok=True)
            
            # Do NOT set offline flags — let it download if missing.
            # It will cache in /data/hub and be instant on restarts.
            _embedder = SentenceTransformer(
                'all-MiniLM-L6-v2',
                device='cpu',
                cache_folder=cache_dir,
            )
            print("[jarvis] Embedder loaded successfully", flush=True)
        except Exception as e:
            print(f"[jarvis] Embedder load failed: {e}", flush=True)
            _embedder = "failed"
    return _embedder if _embedder != "failed" else None

async def find_relevant_tools(prompt: str, top_k: int = 3) -> List[Dict]:
    """Retrieve the most relevant tool schemas using embedding similarity."""
    print("[jarvis] find_relevant_tools called", flush=True)
    embedder = _get_embedder()
    print(f"[jarvis] Embedder status: {'OK' if embedder else 'FAILED'}", flush=True)
    if not embedder:
        return []

    tool_descriptions = []
    tool_objects = []
    for name, tool in _TOOLS.items():
        desc = f"{name}: {tool.description}"
        tool_descriptions.append(desc)
        tool_objects.append({
            "name": name,
            "description": tool.description,
            "parameters": _simplify_schema(tool.parameters)
        })

    print(f"[jarvis] Found {len(tool_descriptions)} tools for RAG", flush=True)
    if not tool_descriptions:
        return []

    try:
        prompt_emb = embedder.encode(prompt, convert_to_tensor=True)
        tool_embs = embedder.encode(tool_descriptions, convert_to_tensor=True)

        import torch
        cos_scores = torch.nn.functional.cosine_similarity(prompt_emb, tool_embs)
        top_results = torch.topk(cos_scores, k=min(top_k, len(tool_objects)))

        selected_tools = [tool_objects[idx] for idx in top_results.indices]
        return selected_tools
    except Exception as e:
        print(f"[jarvis] Embedding search failed: {e}", flush=True)
        return []

async def select_tool_via_local_llm(prompt: str, tools: List[Dict], model_path: Optional[str] = None) -> Optional[Dict]:
    """Use the local GGUF model to select a tool and extract arguments."""
    print(f"[jarvis] Local LLM enabled: {local_llm.is_enabled()}", flush=True)
    if not local_llm.is_enabled():
        print("[jarvis] Local LLM is disabled or missing path", flush=True)
        return None

    # Check if model is loaded
    if hasattr(local_llm, 'is_loaded') and not local_llm.is_loaded():
        print("[jarvis] Model not yet loaded (downloading in background) — falling back to cloud", flush=True)
        return None

    tool_json = json.dumps(tools, indent=2)
    system_prompt = (
        "You are a tool router. Given a user request and a list of tools, select the best tool and provide the arguments.\n"
        "Output ONLY a JSON object with keys 'tool' and 'args'. Do not add any explanation.\n"
        f"Available tools:\n{tool_json}"
    )

    


    # Call the local LLM (MiniCPM) to select the tool
    result = await local_llm.chat(
        prompt=prompt,
        system=system_prompt,
        history=None,
        tools=None,
        timeout=300.0
    )

    print(f"[jarvis] DEBUG Result: ok={result.get('ok')} content_len={len(result.get('content') or '')} error={result.get('error')}", flush=True)
    if not result.get("ok"):
        print(f"[jarvis] Local model failed: {result.get('error')}", flush=True)
        return None

    content = result.get("content", "").strip()
    print(f"[jarvis] Local model response: {content[:500]}", flush=True)

    # Part 295: Strip <think> blocks before parsing (they may contain incomplete JSON)
    import re
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
        print(f"[jarvis] Stripped think block, parsing: {content[:200]}", flush=True)

    # --- Robust JSON parsing strategies ---

    # 0. Repair truncated JSON by adding closing braces
    import re as _re
    _repaired = content.strip()
    # Count braces to see if we're missing any
    for _ in range(3):  # Try up to 3 closing braces
        try:
            _parsed = json.loads(_repaired)
            if isinstance(_parsed, dict) and "tool" in _parsed and "args" in _parsed:
                print(f"[jarvis] Parsed JSON after repairing (added {'}' * _} closing braces)", flush=True)
                return _parsed
        except Exception:
            pass
        if _repaired.endswith("}"):
            # Already ends with }, try adding another
            _repaired = _repaired + "}"
        else:
            _repaired = _repaired + "}"

    # 1. Try direct JSON parse of the whole content
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "tool" in parsed and "args" in parsed:
            print("[jarvis] Parsed JSON directly", flush=True)
            return parsed
    except Exception:
        pass

    # 2. Try to extract JSON from a code block (```json ... ```)
    json_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_block:
        try:
            parsed = json.loads(json_block.group(1))
            if "tool" in parsed and "args" in parsed:
                print("[jarvis] Parsed JSON from code block", flush=True)
                return parsed
        except Exception:
            pass

    # 3. Try to find a JSON object anywhere in the text
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = content[start:end+1]
            parsed = json.loads(json_str)
            if "tool" in parsed and "args" in parsed:
                print("[jarvis] Parsed JSON via substring", flush=True)
                return parsed
    except Exception:
        pass

    # 4. Fallback: Try to find a JSON-like object with tool and args keys
    simple_match = re.search(r'\{\s*"tool"\s*:\s*"[^"]+"\s*,\s*"args"\s*:\s*\{.*?\}\s*\}', content, re.DOTALL)
    if simple_match:
        try:
            parsed = json.loads(simple_match.group(0))
            if "tool" in parsed and "args" in parsed:
                print("[jarvis] Parsed JSON via simple regex", flush=True)
                return parsed
        except Exception:
            pass

    print("[jarvis] Failed to parse any valid JSON from local model response", flush=True)
    return None

async def jarvis_route(prompt: str) -> Optional[Dict]:
    """Full Jarvis pipeline: keyword match -> RAG -> Needle 3 -> MiniCPM."""
    print(f"[jarvis] ROUTE CALLED with prompt: {prompt[:50]}", flush=True)

    tool_keywords = ["calculate", "math", "time", "weather", "search", "web", "http", "file", "read", "write", "pdf", "excel", "sql", "csv", "email", "webhook", "schedule", "kpi", "chart", "narrate", "financial", "stock", "option", "risk", "insurance", "python", "run code", "query", "select", "insert", "update", "delete", "list", "show"]
    p_lower = prompt.lower()
    if not any(kw in p_lower for kw in tool_keywords):
        print("[jarvis] No tool keywords. Bypassing local model entirely.", flush=True)
        return None

    
    # Bypass for greetings
    p_lower = prompt.lower().strip()
    if len(p_lower) < 20 and any(p_lower.startswith(g) for g in ["hi", "hello", "hey", "who are you", "what's up", "how are you"]):
        print("[jarvis] Skipping tool routing for greeting/simple chat", flush=True)
        return None

    # STAGE 0: Deterministic keyword router (100% accurate, 0ms)
    try:
        from .keyword_router import keyword_route
        kw_result = keyword_route(prompt)
        if kw_result:
            print(f"[keyword] Matched: {kw_result['tool']}", flush=True)
            return kw_result
    except Exception as e:
        print(f"[keyword] Error: {e}", flush=True)

    # STAGE 1: RAG shortlist
    shortlist = await find_relevant_tools(prompt, top_k=15)
    if not shortlist:
        return None
    print(f"[jarvis] Shortlist contains {len(shortlist)} tools", flush=True)

    # STAGE 2: Needle 3 on the shortlist
    try:
        from .needle_router import try_needle_route
        from .needle_tool_loader import build_schema_from_tool
        shortlist_schemas = [build_schema_from_tool(tool) for tool in shortlist]
        needle_result = await try_needle_route(prompt, shortlist_schemas)
        if needle_result:
            # Part 396: Save tool call to shared memory
            write_memory("last_tool_execution", needle_result)
            return needle_result
    except Exception as e:
        print(f"[jarvis] Needle skipped: {e}", flush=True)

    # STAGE 3: Fallback to MiniCPM5-2B
    print("[jarvis] Falling back to MiniCPM5-2B.", flush=True)
    # Send only the RAG shortlist (15 tools) to MiniCPM to fit in context
    print(f"[jarvis] Sending {len(shortlist)} shortlisted tools to MiniCPM", flush=True)
    selected = await select_tool_via_local_llm(prompt, shortlist)
    if selected:
        print(f"[jarvis] Selected tool: {selected.get('tool')}", flush=True)
        return selected
        
    print("[jarvis] Local model did not select a tool", flush=True)
    return None

