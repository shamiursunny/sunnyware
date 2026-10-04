# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Echo tool — sanity check / testing."""


class EchoTool:
    name = "echo"
    description = "Echo back the provided text. Useful for testing tool dispatch."
    parameters = {
        "text": {
            "type": "string",
            "description": "Text to echo back",
            "required": True,
        }
    }

    async def run(self, args: dict) -> dict:
        text = args.get("text", "")
        return {"echoed": text, "length": len(text)}
