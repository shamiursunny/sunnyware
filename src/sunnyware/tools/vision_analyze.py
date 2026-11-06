import os
import base64
import httpx
from pathlib import Path
from .. import paths

class VisionAnalyzeTool:
    name = "vision_analyze"
    description = "Analyze an image (e.g., a chart) using a multimodal LLM."
    keywords = ["analyze image", "vision analyze", "look at image", "describe chart"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The image file in the workspace"},
            "prompt": {"type": "string", "description": "What to ask about the image", "default": "Describe this image in detail."}
        },
        "required": ["filename"]
    }

    async def run(self, filename: str, prompt: str = "Describe this image in detail.", kind: str = "workspace") -> dict:
        base = paths.workspace() if kind == "workspace" else paths.sandbox()
        target = base / Path(filename).name
        
        if not target.exists():
            target = paths.sandbox() / Path(filename).name
            if not target.exists():
                return {"error": f"Image {filename} not found in workspace or sandbox."}

        try:
            with open(target, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            return {"error": f"Failed to read image: {e}"}

        # Try Groq first (vision model, free)
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}"},
                        json={
                            "model": "llama-3.2-11b-vision-preview",
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                                ]
                            }],
                            "max_tokens": 1024
                        }
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"]
                    return {"ok": True, "analysis": text}
            except Exception as e:
                # Fall through to Gemini if Groq fails
                pass

        # Fallback to Gemini
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {"error": "No vision API key found (GROQ_API_KEY or GEMINI_API_KEY)."}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                ]
            }]
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"ok": True, "analysis": text}
        except Exception as e:
            return {"error": f"Vision API failed: {str(e)}"}
