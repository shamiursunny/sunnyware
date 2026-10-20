# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 229: Sliding window rate limiter."""

import time
from collections import defaultdict
from threading import Lock

# In-memory store: { "key_hash": [timestamp1, timestamp2, ...] }
_BUCKETS = defaultdict(list)
_LOCK = Lock()

# Maximum time window in seconds (1 minute)
WINDOW = 60


def check_rate_limit(key_id: str, limit_rpm: int) -> dict:
    """
    Check if the key is within the limit.
    Returns:
      { "allowed": bool, "remaining": int, "reset": float }
    """
    if limit_rpm <= 0:
        # 0 or negative means unlimited
        return {"allowed": True, "remaining": 9999, "reset": 0}

    now = time.time()
    with _LOCK:
        # Clean up old timestamps
        bucket = _BUCKETS[key_id]
        cutoff = now - WINDOW
        bucket[:] = [ts for ts in bucket if ts > cutoff]

        if len(bucket) >= limit_rpm:
            # Rate limited
            oldest = bucket[0] if bucket else now
            reset_in = max(0, oldest + WINDOW - now)
            return {"allowed": False, "remaining": 0, "reset": reset_in}

        # Record this request
        bucket.append(now)
        remaining = limit_rpm - len(bucket)
        return {"allowed": True, "remaining": remaining, "reset": WINDOW}
