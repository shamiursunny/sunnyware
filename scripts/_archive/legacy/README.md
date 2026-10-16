# Legacy smoke tests (archived 2026-10-16, Part 157b)

These 9 smoke tests were written for earlier parts of Sunnyware and
became stale as later parts changed the code they asserted against.
They are kept for git history and can be run manually if you want to
revisit the exact behavior they checked. They are NOT run by
`scripts/ship.py` (its glob is `scripts/smoke_test_part*.py` at the
top level only).

## Why each was archived

### smoke_test_part39.py, part40.py
  Tested: WebUI embedded JavaScript contains no raw newlines inside
          string literals (a Part 34-38-era regression guard).
  Obsolete because: `webui.py` was substantially rewritten in later
          parts. The assertion targets an old HTML/JS structure that
          no longer exists.

### smoke_test_part41.py
  Tested: WebUI regression guard (part of the Part 34-44 UI series).
  Obsolete because: superseded by later UI smokes. Archived for
          consistency with siblings 39/40/42/43/44.

### smoke_test_part42.py, part43.py
  Tested: `marked.js` CDN presence and version pinning.
  Obsolete because: `marked.min.js` is now self-hosted at
          `src/sunnyware/static/marked.min.js` (no CDN reference).

### smoke_test_part44.py
  Tested: mobile/tv-mode CSS classes + initMobileMenu + marked CDN.
  Obsolete because: the WebUI was rebuilt (mobile menu renamed,
          tv-mode replaced by responsive breakpoints).

### smoke_test_part99.py
  Tested: provider pre-filter skips oversized providers.
  Superseded by: Part 144 (tool-aware eligibility).
          Current behavior covered by smoke_test_part144.py.

### smoke_test_part102.py
  Tested: retry handler reloads providers, 20s threshold, 8s wait cap.
  Superseded by: Part 153 removed reload=True; Part 154 raised
          threshold to 40s and cap to _retry_wait_max + 5s.
          Current behavior covered by 153.py and 154.py.

### smoke_test_part129.py
  Tested: `roles count == 9`.
  Obsolete because: Part 142a added the `auditor` role (now 10).
          Current coverage in 142a.py + 151.py.

## If you want coverage back

Recreate as `scripts/smoke_test_partNNN_<feature>.py` targeting the
CURRENT code shape. The archived file is a good starting template --
just update the hard-coded assertions.
