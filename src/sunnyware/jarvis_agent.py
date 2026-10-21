# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""
Local Jarvis Agent for token-efficient tool calling.
Uses sentence-transformers for tool retrieval and llama-cpp-python for local tool selection.
"""

import json
import os
import asyncio
import re
from typing import List, Dict, Any, Optional
from . import local_llm_s3 as local_llm
from .tools import _TOOLS, get_tool, list_tools

# Lazy load embedding model
_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("[jarvis] Loading embedding model...", flush=True)
            _embedder = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
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
            "parameters": tool.parameters
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

    result = await local_llm.chat(
        prompt=prompt,
        system=system_prompt,
        history=None,
        tools=None,
        timeout=45.0
    )

    if not result.get("ok"):
        print(f"[jarvis] Local model failed: {result.get('error')}", flush=True)
        return None

    content = result.get("content", "").strip()
    print(f"[jarvis] Local model response: {content[:500]}", flush=True)

    # --- Robust JSON parsing strategies ---

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
    """Full Jarvis pipeline: retrieve relevant tools, select one with the local model."""
    print(f"[jarvis] ROUTE CALLED with prompt: {prompt[:50]}", flush=True)
    relevant_tools = await find_relevant_tools(prompt, top_k=3)
    if not relevant_tools:
        return None

    selected = await select_tool_via_local_llm(prompt, relevant_tools)
    if selected:
        print(f"[jarvis] Selected tool: {selected.get('tool')}", flush=True)
    else:
        print("[jarvis] Local model did not select a tool", flush=True)
    return selected
