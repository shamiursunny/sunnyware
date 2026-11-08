#!/usr/bin/env python3
"""Verify the blockchain-style attestation hash ladder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hash_chain


def main():
    summary = hash_chain.chain_summary()
    print("=" * 60)
    print("  ATTESTATION CHAIN")
    print("=" * 60)
    if summary["length"] == 0:
        print("  (empty — no attestation runs have been chained yet)")
        return 0

    print(f"  Blocks:   {summary['length']}")
    print(f"  Latest:   {summary['latest_block_hash'][:32]}...")
    print(f"  Commit:   {summary['latest_commit']}")
    print(f"  When:     {summary['latest_timestamp']}")
    print()
    ok, errors = hash_chain.verify_chain()
    if ok:
        print(f"  [PASS] chain integrity verified ({summary['length']} blocks)")
        return 0
    print(f"  [FAIL] {len(errors)} error(s) in chain:")
    for e in errors:
        print(f"    - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
