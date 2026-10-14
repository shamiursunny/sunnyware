# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Echo tool — sanity check / testing ONLY."""


class EchoTool:
    name = "echo"
    description = (
        "TEST-ONLY tool. Echoes back the provided text. NEVER use this for "
        "user requests — it is only for internal smoke tests. If the user "
        "says hi/hello/thanks, reply directly with text, do not call echo."
    )
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
