"""Blockchain-style hash ladder for attestation reports.

Each attestation run appends a block whose hash depends on the previous
block's hash, forming an append-only chain. Tampering with any historical
report breaks all subsequent blocks.

Schema (reports/CHAIN.json — a JSON array):
    [
      {
        "index": 0,
        "timestamp_utc": "...",
        "commit": "abc1234",
        "version": "1.17.0",
        "combined_hash": "sha256(sorted name:hash pairs of this run)",
        "prev_block_hash": "0"*64 (genesis for index 0),
        "block_hash": "sha256(prev_block_hash + '\n' + combined_hash)"
      },
      ...
    ]
"""
import json
import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHAIN_PATH = REPO / "reports" / "CHAIN.json"
GENESIS = "0" * 64


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_combined(reports: dict) -> str:
    """Deterministic hash of all script hashes, sorted by script name."""
    items = sorted((name, (r or {}).get("sha256", "")) for name, r in reports.items())
    payload = "\n".join(f"{n}:{h}" for n, h in items)
    return _sha256(payload)


def load_chain() -> list:
    """Read the chain file. Returns [] if missing/corrupt."""
    if not CHAIN_PATH.exists():
        return []
    try:
        data = json.loads(CHAIN_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_prev_block_hash() -> str:
    chain = load_chain()
    if not chain:
        return GENESIS
    return chain[-1].get("block_hash", GENESIS)


def append_block(manifest: dict) -> dict:
    """Append a new block for this manifest. Returns the (possibly updated) manifest.

    Idempotent: if the manifest already has a 'chain' field with the same
    combined_hash as the last block, it will NOT append a duplicate.
    Never raises — wraps everything in try/except so it can't break the ship pipeline.
    """
    try:
        combined = compute_combined(manifest.get("reports", {}))
        chain = load_chain()

        # Idempotency: skip if the last block already matches this run
        if chain and chain[-1].get("combined_hash") == combined \
                and chain[-1].get("commit") == manifest.get("commit_short"):
            manifest["chain"] = chain[-1]
            return manifest

        prev = chain[-1]["block_hash"] if chain else GENESIS
        block_hash = _sha256(f"{prev}\n{combined}")
        block = {
            "index": len(chain),
            "timestamp_utc": manifest.get("timestamp_utc"),
            "commit": manifest.get("commit_short"),
            "version": manifest.get("version"),
            "combined_hash": combined,
            "prev_block_hash": prev,
            "block_hash": block_hash,
        }
        chain.append(block)
        CHAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHAIN_PATH.write_text(json.dumps(chain, indent=2), encoding="utf-8")
        manifest["chain"] = block
        return manifest
    except Exception:
        return manifest


def verify_chain() -> tuple:
    """Walk the chain. Returns (ok: bool, errors: list[str])."""
    errors = []
    try:
        chain = load_chain()
        if not chain:
            return True, []
        prev = GENESIS
        for i, block in enumerate(chain):
            idx = block.get("index")
            if idx != i:
                errors.append(f"block {i}: index mismatch (got {idx})")
            recorded_prev = block.get("prev_block_hash", "")
            if recorded_prev != prev:
                errors.append(
                    f"block {i}: prev mismatch (expected {prev[:16]}.., "
                    f"got {recorded_prev[:16]}..)"
                )
            combined = block.get("combined_hash", "")
            expected = _sha256(f"{recorded_prev}\n{combined}")
            actual = block.get("block_hash", "")
            if expected != actual:
                errors.append(
                    f"block {i}: hash mismatch (expected {expected[:16]}.., "
                    f"got {actual[:16]}..)"
                )
            prev = actual
        return (len(errors) == 0, errors)
    except Exception as e:
        return False, [f"verify exception: {type(e).__name__}: {e}"]


def chain_summary() -> dict:
    """Return a compact summary for reporting."""
    chain = load_chain()
    if not chain:
        return {"length": 0, "latest": None, "genesis": GENESIS}
    latest = chain[-1]
    return {
        "length": len(chain),
        "latest_block_hash": latest.get("block_hash"),
        "latest_commit": latest.get("commit"),
        "latest_timestamp": latest.get("timestamp_utc"),
        "genesis": GENESIS,
    }
