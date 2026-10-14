# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Image generation tool (Part 98).

Generates an image from a text prompt via Pollinations.AI free tier
(no API key required). Returns {image_base64, image_format, ...} so
the WebUI renders it inline -- same contract as chart_from_data.
"""
import base64
import os

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False


_ALLOWED_MODELS = {"flux", "turbo", "gptimage", "qwen-image", "kontext", "nanobanana"}
_DEFAULT_MODEL = "flux"
_DEFAULT_SIZE = 1024
_MAX_SIZE = 2048
_MIN_SIZE = 128
_TIMEOUT = 45.0
# Free tier caps at ~768px output and ~500 KB file.
_MAX_BYTES = 2 * 1024 * 1024


class ImageGenerateTool:
    name = "image_generate"
    description = (
        "Generate a NEW image from a text prompt using Pollinations.AI "
        "(free tier, no API key). Use whenever the user asks to draw, "
        "generate, create, illustrate, or visualize something as a picture. "
        "Returns base64 image data that renders inline in the chat. "
        "Models: flux (default, best quality), turbo (fast), gptimage, "
        "qwen-image, kontext, nanobanana. "
        "IMPORTANT: Call this tool EXACTLY ONCE per user request. The free "
        "tier is rate-limited to 1 request per 15 seconds, so a second "
        "call within that window will fail. Do not generate variations "
        "unless the user explicitly asks for multiple images."
    )
    parameters = {
        "prompt": {
            "type": "string",
            "description": "Text description of the image to generate",
            "required": True,
        },
        "model": {
            "type": "string",
            "description": "One of: flux, turbo, gptimage, qwen-image, kontext, nanobanana (default: flux)",
            "required": False,
        },
        "width": {
            "type": "integer",
            "description": "Image width in pixels (default: 1024, range 128-2048)",
            "required": False,
        },
        "height": {
            "type": "integer",
            "description": "Image height in pixels (default: 1024, range 128-2048)",
            "required": False,
        },
        "seed": {
            "type": "integer",
            "description": "Optional seed for reproducible generation",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_HTTPX:
            return {"error": "httpx not available in this environment"}

        prompt = (args.get("prompt") or "").strip()
        if not prompt:
            return {"error": "prompt is required"}
        if len(prompt) > 2000:
            return {"error": "prompt too long (max 2000 chars)"}

        model = (args.get("model") or _DEFAULT_MODEL).strip().lower()
        if model not in _ALLOWED_MODELS:
            return {"error": f"model must be one of {sorted(_ALLOWED_MODELS)}"}

        try:
            width = int(args.get("width") or _DEFAULT_SIZE)
            height = int(args.get("height") or _DEFAULT_SIZE)
        except (TypeError, ValueError):
            return {"error": "width/height must be integers"}
        width = max(_MIN_SIZE, min(_MAX_SIZE, width))
        height = max(_MIN_SIZE, min(_MAX_SIZE, height))

        # Pollinations free image endpoint
        base = os.getenv("POLLINATIONS_IMAGE_BASE_URL", "https://image.pollinations.ai")
        # URL-encode the prompt inline (Pollinations accepts it in the path)
        from urllib.parse import quote
        url = f"{base}/prompt/{quote(prompt, safe='')}"

        params = {
            "model": model,
            "width": width,
            "height": height,
            "nologo": "true",
        }
        seed = args.get("seed")
        if seed is not None:
            try:
                params["seed"] = int(seed)
            except (TypeError, ValueError):
                pass

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(url, params=params)
        except Exception as e:
            return {"error": f"request failed: {type(e).__name__}: {e}"}

        if r.status_code != 200:
            return {
                "error": f"Pollinations returned HTTP {r.status_code}",
                "detail": (r.text or "")[:300],
            }

        raw = r.content
        if not raw:
            return {"error": "empty image response"}
        if len(raw) > _MAX_BYTES:
            return {"error": f"image too large ({len(raw)} bytes > {_MAX_BYTES})"}

        # Pollinations returns JPEG by default; detect via magic bytes
        fmt = "png"
        if raw[:3] == b"\xff\xd8\xff":
            fmt = "jpeg"
        elif raw[:8] == b"\x89PNG\r\n\x1a\n":
            fmt = "png"
        elif raw[:4] == b"RIFF":
            fmt = "webp"

        return {
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "image_format": fmt,
            "image_bytes": len(raw),
            "model": model,
            "prompt": prompt[:200],
            "width": width,
            "height": height,
        }
