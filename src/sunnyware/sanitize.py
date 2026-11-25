# SPDX-License-Identifier: AGPL-3.0-only
# Module: sanitize — feature-flagged, zero-token, opt-in
import os, re

_ENABLED = os.getenv("SUNNYWARE_SANITIZE_ARGS", "0") == "1"
_MAX = int(os.getenv("SUNNYWARE_MAX_ARG_LEN", "10000"))
_SCRIPT = re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL)

def sanitize_args(args: dict) -> dict:
    if not _ENABLED:
        return args
    out = {}
    for k, v in args.items():
        if isinstance(v, str):
            v = _SCRIPT.sub("", v)
            if len(v) > _MAX:
                v = v[:_MAX] + "…"
        out[k] = v
    return out
