# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""
Local Jarvis Agent for token-efficient tool calling.
Uses sentence-transformers for tool retrieval and llama-cpp-python for local tool selection.
"""

import json
import os
import asyncio

from typing import List, Dict, Any, Optional
from . import local_llm_s3 as local_llm
from .tools import _TOOLS, get_tool, list_tools

# Lazy load embedding model
_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            print("[jarvis] Loading embedding model...")
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"[jarvis] Embedder load failed: {e}")
            _embedder = "failed"
    return _embedder if _embedder != "failed" else None

async def find_relevant_tools(prompt: str, top_k: int = 3) -> List[Dict]:
    print("[jarvis] find_relevant_tools called")
    """Retrieve the most relevant tool schemas using embedding similarity."""
    embedder = _get_embedder()
    print(f"[jarvis] Embedder status: {'OK' if embedder else 'FAILED'}")
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

    print(f"[jarvis] Found {len(tool_descriptions)} tools for RAG")
    if not tool_descriptions:
        print("[jarvis] No tools available for RAG")
        return []

    # Embed prompt and tool descriptions
    prompt_emb = embedder.encode(prompt, convert_to_tensor=True)
    tool_embs = embedder.encode(tool_descriptions, convert_to_tensor=True)

    # Compute cosine similarity
    import torch
    cos_scores = torch.nn.functional.cosine_similarity(prompt_emb, tool_embs)
    top_results = torch.topk(cos_scores, k=min(top_k, len(tool_objects)))

    selected_tools = [tool_objects[idx] for idx in top_results.indices]
    return selected_tools

async def select_tool_via_local_llm(prompt: str, tools: List[Dict], model_path: Optional[str] = None) -> Optional[Dict]:
    """
    Use the local GGUF model to select a tool and extract arguments.
    Returns a dict like {"tool": "calculator", "args": {"expression": "2+2"}} or None.
    """
    print(f"[jarvis] Local LLM enabled: {local_llm.is_enabled()}")
    if not local_llm.is_enabled():
        print("[jarvis] Local LLM is disabled or missing path")
        return None

    # Construct a concise prompt
    tool_json = json.dumps(tools, indent=2)
    system_prompt = (
        "You are a tool router. Given a user request and a list of tools, select the best tool and provide the arguments.\n"
        "Output ONLY a JSON object with keys 'tool' and 'args'. Do not add any explanation.\n"
        f"Available tools:\n{tool_json}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    # Call local model with a small max_tokens to encourage brevity
    result = await local_llm.chat(
        prompt=prompt,
        system=system_prompt,
        history=None,
        tools=None,  # We pass tools via the system prompt for better control
        timeout=15.0
    )

    if not result.get("ok"):
        return None

    content = result.get("content", "").strip()
    print(f"[jarvis] Local model response: {content[:200]}")
    # Extract JSON from the response (the model might wrap it in markdown)
    try:
        # Find the first { and last }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            json_str = content[start:end+1]
            parsed = json.loads(json_str)
            if "tool" in parsed and "args" in parsed:
                return parsed
    except Exception as e:
        print(f"[jarvis] JSON parse failed: {e}")
    return None

async def jarvis_route(prompt: str) -> Optional[Dict]:
    print(f"[jarvis] ROUTE CALLED with prompt: {prompt[:50]}")
    """
    Full Jarvis pipeline: retrieve relevant tools, select one with the local model.
    Returns {"tool": ..., "args": ...} or None.
    """
    # Step 1: Retrieve top tools
    relevant_tools = await find_relevant_tools(prompt, top_k=3)
    if not relevant_tools:
        return None

    # Step 2: Local LLM selects the tool
    selected = await select_tool_via_local_llm(prompt, relevant_tools)
    if selected:
        print(f"[jarvis] Selected tool: {selected.get('tool')}")
    else:
        print("[jarvis] Local model did not select a tool")
    return selected
