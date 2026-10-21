# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""
S3-backed local LLM loader.
Downloads GGUF from HF S3 bucket to a local cache, then loads with llama-cpp-python.
"""

import asyncio
import os
import time
from typing import Optional

_LOCK = asyncio.Lock()
_MODEL = None
_LOAD_ERROR: str = ""
_DOWNLOADED_PATH: str = ""

def is_loaded() -> bool:
    return _MODEL is not None

def _enabled() -> bool:
    return (os.getenv("LOCAL_MODEL_ENABLED", "0") or "0").strip() in ("1", "true", "yes")

def is_enabled() -> bool:
    return _enabled() and bool(os.getenv("S3_BUCKET_NAME"))

def _load_sync():
    global _MODEL, _LOAD_ERROR, _DOWNLOADED_PATH
    if _MODEL is not None:
        return _MODEL

    import boto3
    from botocore.config import Config

    bucket = os.getenv("S3_BUCKET_NAME", "")
    key = os.path.basename(os.getenv("LOCAL_MODEL_PATH", ""))
    if not bucket or not key:
        _LOAD_ERROR = "S3_BUCKET_NAME or LOCAL_MODEL_PATH not set"
        raise RuntimeError(_LOAD_ERROR)

    # Part 288: First, check if the model is already mounted at /models (read-only)
    mounted_path = os.path.join("/models", os.path.basename(key))
    if os.path.exists(mounted_path):
        print(f"[jarvis] Found model at mounted path: {mounted_path} — skipping download", flush=True)
        local_path = mounted_path
        _DOWNLOADED_PATH = local_path
    else:
        # Fallback: download to /data/models if not mounted
        cache_dir = "/data/models"
        os.makedirs(cache_dir, exist_ok=True)
        local_path = os.path.join(cache_dir, os.path.basename(key))
        _DOWNLOADED_PATH = local_path

        if not os.path.exists(local_path) or os.path.getsize(local_path) < 1000000000:
            print(f"[jarvis] Downloading {key} from s3://{bucket} to {local_path} ...", flush=True)
            s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL", "https://s3.hf.co/shamiur"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(
                region_name="us-east-1",
                s3={"addressing_style": "path"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        from botocore.config import Config as _BotoConfig
        _dl_cfg = _BotoConfig(read_timeout=300, connect_timeout=30)
        s3.download_file(bucket, key, local_path, Config=_dl_cfg)
        print(f"[jarvis] Download complete: {local_path}")
    else:
        print(f"[jarvis] Model already cached at {local_path}")

    try:
        from llama_cpp import Llama
    except Exception as e:
        _LOAD_ERROR = "llama_cpp import failed: " + str(e)
        raise

    try:
        _MODEL = Llama(
            model_path=local_path,
            n_ctx=int(os.getenv("LOCAL_MODEL_CTX", "4096")),
            n_threads=int(os.getenv("LOCAL_MODEL_THREADS", "2")),
            n_batch=256,
            use_mlock=False,
            verbose=False,
        )
        _LOAD_ERROR = ""
        return _MODEL
    except Exception as e:
        _LOAD_ERROR = "load failed: " + str(e)
        raise

async def _ensure_loaded():
    if _MODEL is not None:
        return _MODEL
    return await asyncio.to_thread(_load_sync)

async def chat(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[list] = None,
    tools: Optional[list] = None,
    timeout: float = 120.0,
) -> dict:
    if not is_enabled():
        return {"ok": False, "error": "local model not enabled", "provider": "local"}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    start = time.time()
    async with _LOCK:
        try:
            llama = await _ensure_loaded()
        except Exception as e:
            return {"ok": False, "error": f"load failed: {e}", "provider": "local"}

        def _run():
            kwargs = {"messages": messages, "temperature": 0.2, "max_tokens": 800, "stream": False}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            return llama.create_chat_completion(**kwargs)

        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "local model timeout", "provider": "local"}

    latency_ms = int((time.time() - start) * 1000)
    msg = resp["choices"][0]["message"]
    return {
        "ok": True,
        "content": (msg.get("content") or "").strip(),
        "tool_calls": msg.get("tool_calls") or None,
        "provider": "local_s3",
        "latency_ms": latency_ms,
    }

async def preload() -> dict:
    if not is_enabled():
        return {"status": "disabled"}
    try:
        await _ensure_loaded()
        return {"status": "loaded", "path": _DOWNLOADED_PATH}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def status() -> dict:
    return {
        "enabled": is_enabled(),
        "bucket": os.getenv("S3_BUCKET_NAME", "(not set)"),
        "key": os.getenv("LOCAL_MODEL_PATH", "(not set)"),
        "loaded": _MODEL is not None,
        "load_error": _LOAD_ERROR,
        "downloaded_path": _DOWNLOADED_PATH,
    }
