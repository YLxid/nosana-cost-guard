#!/usr/bin/env python3
"""Verify the hash chain in audit.log.jsonl (see guard.py).

Recomputes every entry's SHA-256 hash and checks that each entry's
prev_hash matches the previous entry's hash, and that sequence numbers
run 1, 2, 3, ... in order. Any tampering — changing a cost, a decision,
or a timestamp — breaks the chain.

Usage:
  python3 verify.py                  # verify audit.log.jsonl
  python3 verify.py --file other.jsonl
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENESIS_HASH = "0" * 64


def entry_hash(entry_without_hash: dict) -> str:
    canonical = json.dumps(entry_without_hash, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Cost Guard audit log")
    parser.add_argument("--file", type=str, default="audit.log.jsonl",
                        help="Audit log file to verify (default: audit.log.jsonl)")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.is_absolute():
        path = HERE / path
    if not path.is_file():
        print(f"FAILED: audit log not found: {path}")
        print("Run `python3 guard.py --dry-run` first to create it.")
        return 1

    entries = []
    with path.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append((lineno, json.loads(line)))
            except json.JSONDecodeError as exc:
                print(f"FAILED: line {lineno} is not valid JSON — {exc}")
                return 1

    if not entries:
        print(f"FAILED: audit log is empty: {path}")
        return 1

    prev_hash = GENESIS_HASH
    for expected_seq, (lineno, entry) in enumerate(entries, start=1):
        seq = entry.get("seq")
        if seq != expected_seq:
            print(f"FAILED: line {lineno}: seq is {seq}, expected {expected_seq}")
            return 1
        if entry.get("prev_hash") != prev_hash:
            print(
                f"FAILED: line {lineno} (seq {seq}): prev_hash does not "
                f"match the previous entry's hash"
            )
            return 1
        stored = entry.get("hash")
        recomputed = entry_hash({k: v for k, v in entry.items() if k != "hash"})
        if stored != recomputed:
            print(
                f"FAILED: line {lineno} (seq {seq}, "
                f"deployment {entry.get('deployment_id')}): hash mismatch — "
                f"entry was modified after it was written"
            )
            return 1
        prev_hash = stored
        print(
            f"  ok seq={seq} {entry.get('deployment_id')} "
            f"{entry.get('decision')} "
            f"(${entry.get('cost_usd_estimate', 0):.2f})"
        )

    print(f"VERIFIED: {len(entries)} entries, hash chain intact ({path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
