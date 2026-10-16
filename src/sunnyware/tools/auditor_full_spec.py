# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 148a: sidecar loader for the extended auditor spec.

Returns the full ~4K-token extended spec from
  static/auditor_prompt_full.txt

Routine audits run on the compressed prompt (~2.3K chars). When a task
is nuanced (multi-layer root cause, benchmark validation, security
directionality, evidence hierarchy), the auditor can call this tool
to load the extended playbook on demand — the extra tokens are only
consumed for that specific call.
"""

from pathlib import Path


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_SPEC_FILE = _STATIC_DIR / "auditor_prompt_full.txt"


def _read_spec() -> str:
    try:
        if not _SPEC_FILE.exists():
            return ""
        return _SPEC_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""


class AuditorFullSpecTool:
    name = "auditor_full_spec"
    description = (
        "Load the extended auditor specification (~4K tokens). "
        "Call this ONLY when the compressed prompt is insufficient for "
        "a complex audit: multi-layer root cause, benchmark validation, "
        "evidence hierarchy disputes, security directionality, or any "
        "task where the exact V15.0 rule matters. "
        "Do NOT call for simple math/logic checks — those are covered "
        "by the base prompt. Prefer one call; reuse the returned spec "
        "for the rest of the analysis."
    )
    parameters = {
        "section": {
            "type": "string",
            "description": (
                "Optional. Name of a section to emphasize "
                "(e.g. 'CANONICAL TAXONOMY', 'ROOT CAUSE - MULTI-LAYER'). "
                "Leave empty to get the full spec."
            ),
            "required": False,
        }
    }

    async def run(self, args: dict) -> dict:
        try:
            spec = _read_spec()
            if not spec:
                return {
                    "ok": False,
                    "error": "spec_file_missing",
                    "path": str(_SPEC_FILE),
                }
            section = (args or {}).get("section") or ""
            return {
                "ok": True,
                "spec": spec,
                "length": len(spec),
                "section_hint": section,
                "path": str(_SPEC_FILE),
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            }
