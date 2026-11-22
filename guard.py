#!/usr/bin/env python3
"""Nosana Cost Guard — budget guard for Nosana deployments.

Standard library only. No network calls, no credentials needed in
dry-run / check mode.

Modes:
  python3 guard.py --dry-run   Simulate the guard against sample
                               deployments. Nothing is really stopped.
                               Decisions are written to the audit log
                               (marked dry_run=true).
  python3 guard.py --check     Validate config.json (or
                               config.example.json) and
                               job-definition.json. Exits 0 on success.
  python3 guard.py --live      Refuses: live mode is NOT implemented
                               yet (see README.md). It would need a
                               Nosana account + API key, which must
                               never be committed to this repo.

Audit log: audit.log.jsonl, one JSON object per line, hash-chained
with SHA-256. Verify it with:  python3 verify.py
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENESIS_HASH = "0" * 64

# GPU market snapshot, Nov 2026 sources (see README.md).
# Prices change — check the live Nosana dashboard before deploying.
# The picker is only as correct as this table; live lookup is a TODO.
GPU_MARKET = [
    {"gpu": "RTX 3060", "vram_gb": 12, "price_usd_per_hour": 0.048},
    {"gpu": "RTX 3080", "vram_gb": 10, "price_usd_per_hour": 0.096},
    {"gpu": "RTX 5070", "vram_gb": 12, "price_usd_per_hour": 0.15},
    {"gpu": "RTX 4090", "vram_gb": 24, "price_usd_per_hour": 0.40},
    {"gpu": "RTX 5090", "vram_gb": 32, "price_usd_per_hour": 0.48},
    {"gpu": "H100", "vram_gb": 80, "price_usd_per_hour": 1.50},
]

DEFAULT_CONFIG = {
    "idle_minutes": 10,
    "max_spend_usd": 2.0,
    "enforce_simple": True,
    "replica_count": 1,
    "min_vram_gb": 24,
    "container_timeout_minutes": 45,
    "credit_budget_usd": 70.0,
    "gpu_price_usd_per_hour": 0.40,
    "audit_log": "audit.log.jsonl",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_config(path: Path | None) -> tuple[dict, Path]:
    """Load config.json if present, else config.example.json, else defaults."""
    candidates = []
    if path is not None:
        candidates.append(path)
    candidates += [HERE / "config.json", HERE / "config.example.json"]
    for candidate in candidates:
        if candidate.is_file():
            with candidate.open() as f:
                data = json.load(f)
            merged = {**DEFAULT_CONFIG, **data}
            return merged, candidate
    return dict(DEFAULT_CONFIG), HERE / "(built-in defaults)"


def validate_config(config: dict) -> list[str]:
    errors = []
    if not isinstance(config.get("idle_minutes"), (int, float)) or config["idle_minutes"] <= 0:
        errors.append("idle_minutes must be a number > 0")
    if not isinstance(config.get("max_spend_usd"), (int, float)) or config["max_spend_usd"] <= 0:
        errors.append("max_spend_usd must be a number > 0")
    if config.get("replica_count") != 1:
        errors.append(f"replica_count must be 1 for test runs (got {config.get('replica_count')})")
    if not isinstance(config.get("min_vram_gb"), (int, float)) or config["min_vram_gb"] <= 0:
        errors.append("min_vram_gb must be a number > 0")
    timeout = config.get("container_timeout_minutes")
    if not isinstance(timeout, (int, float)) or not (1 <= timeout <= 360):
        errors.append("container_timeout_minutes must be between 1 and 360")
    if not isinstance(config.get("credit_budget_usd"), (int, float)) or config["credit_budget_usd"] <= 0:
        errors.append("credit_budget_usd must be a number > 0")
    return errors


def load_job_definition(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def validate_job_definition(job: dict) -> list[str]:
    errors = []
    if job.get("version") != "0.1":
        errors.append(f"job version must be '0.1' (got {job.get('version')!r})")
    ops = job.get("ops")
    if not isinstance(ops, list) or not ops:
        errors.append("job.ops must be a non-empty list")
        return errors
    op = ops[0]
    args = op.get("args", {}) if isinstance(op, dict) else {}
    image = str(args.get("image", ""))
    if "ollama" not in image:
        errors.append(f"job image must be an Ollama image (got {image!r})")
    if args.get("gpu") is not True:
        errors.append("job must request a GPU (args.gpu must be true)")
    cmd = " ".join(str(c) for c in args.get("cmd", []))
    if "qwen3:8b" not in cmd:
        errors.append("job command must pull qwen3:8b")
    dep = job.get("deployment", {}) if isinstance(job.get("deployment"), dict) else {}
    if dep.get("strategy") != "SIMPLE":
        errors.append(f"deployment.strategy must be SIMPLE (got {dep.get('strategy')!r}) — Infinite burns credits")
    if dep.get("replica_count") != 1:
        errors.append(f"deployment.replica_count must be 1 (got {dep.get('replica_count')!r})")
    timeout = dep.get("container_timeout_minutes")
    if not isinstance(timeout, (int, float)) or not (30 <= timeout <= 60):
        errors.append(f"deployment.container_timeout_minutes must be 30–60 for test runs (got {timeout!r})")
    if dep.get("min_vram_gb", 0) < 24:
        errors.append("deployment.min_vram_gb must be >= 24 for qwen3:8b")
    return errors


def pick_cheapest_gpu(min_vram_gb: float) -> dict | None:
    """Cheapest GPU market meeting the minimum VRAM requirement."""
    eligible = [g for g in GPU_MARKET if g["vram_gb"] >= min_vram_gb]
    if not eligible:
        return None
    return min(eligible, key=lambda g: g["price_usd_per_hour"])


def evaluate(deployment: dict, config: dict) -> tuple[str, list[str], float]:
    """Apply the guard rules. Returns (decision, reasons, cost estimate)."""
    reasons: list[str] = []
    runtime_hours = deployment["runtime_minutes"] / 60.0
    cost = round(runtime_hours * deployment["price_usd_per_hour"], 4)

    if config.get("enforce_simple") and deployment.get("strategy") != "SIMPLE":
        reasons.append(
            f"strategy is {deployment.get('strategy')} (must be SIMPLE)"
        )
    if deployment.get("replicas", 1) != 1:
        reasons.append(f"replicas is {deployment.get('replicas')} (must be 1)")
    if deployment["idle_minutes"] > config["idle_minutes"]:
        reasons.append(
            f"idle {deployment['idle_minutes']} min > "
            f"{config['idle_minutes']} min limit"
        )
    if cost > config["max_spend_usd"]:
        reasons.append(
            f"spend ${cost:.2f} > ${config['max_spend_usd']:.2f} cap"
        )
    decision = "STOP" if reasons else "KEEP"
    return decision, reasons, cost


def sample_deployments() -> list[dict]:
    """Sample data for --dry-run only. No live Nosana data is used."""
    return [
        {
            "id": "ollama-test-01",
            "gpu": "RTX 4090",
            "price_usd_per_hour": 0.40,
            "runtime_minutes": 35,
            "idle_minutes": 12,
            "requests": 10,
            "strategy": "SIMPLE",
            "replicas": 1,
        },
        {
            "id": "ollama-test-02",
            "gpu": "RTX 4090",
            "price_usd_per_hour": 0.40,
            "runtime_minutes": 15,
            "idle_minutes": 3,
            "requests": 4,
            "strategy": "SIMPLE",
            "replicas": 1,
        },
        {
            "id": "ollama-test-03",
            "gpu": "RTX 5090",
            "price_usd_per_hour": 0.48,
            "runtime_minutes": 300,
            "idle_minutes": 0,
            "requests": 120,
            "strategy": "Infinite",
            "replicas": 1,
        },
    ]


def _entry_hash(entry_without_hash: dict) -> str:
    canonical = json.dumps(entry_without_hash, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit_log(log_path: Path, entries: list[dict]) -> list[dict]:
    """Append entries to a hash-chained JSONL audit log."""
    prev_hash = GENESIS_HASH
    seq = 0
    if log_path.is_file():
        with log_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    old = json.loads(line)
                except json.JSONDecodeError:
                    continue
                prev_hash = old.get("hash", prev_hash)
                seq = max(seq, int(old.get("seq", 0)))
    written = []
    with log_path.open("a") as f:
        for entry in entries:
            seq += 1
            full = {
                "seq": seq,
                "timestamp": now_iso(),
                **entry,
                "prev_hash": prev_hash,
            }
            full["hash"] = _entry_hash(full)
            f.write(json.dumps(full, sort_keys=True) + "\n")
            prev_hash = full["hash"]
            written.append(full)
    return written


def cmd_check(config_path: Path | None) -> int:
    config, source = load_config(config_path)
    print(f"config: {source}")
    errors = validate_config(config)
    if errors:
        print("config: FAILED")
        for e in errors:
            print(f"  - {e}")
    else:
        print(
            f"config: OK (idle={config['idle_minutes']} min, "
            f"max_spend=${config['max_spend_usd']:.2f}, "
            f"replicas={config['replica_count']}, "
            f"min_vram={config['min_vram_gb']} GB, "
            f"timeout={config['container_timeout_minutes']} min, "
            f"budget=${config['credit_budget_usd']:.2f})"
        )

    job_path = HERE / "job-definition.json"
    if not job_path.is_file():
        print("job-definition.json: MISSING")
        return 1
    try:
        job = load_job_definition(job_path)
    except json.JSONDecodeError as exc:
        print(f"job-definition.json: INVALID JSON — {exc}")
        return 1
    job_errors = validate_job_definition(job)
    if job_errors:
        print("job-definition.json: FAILED")
        for e in job_errors:
            print(f"  - {e}")
    else:
        dep = job["deployment"]
        print(
            f"job-definition.json: OK (Ollama {dep['model']}, "
            f"{dep['gpu_model']}, {dep['strategy']}, "
            f"replicas={dep['replica_count']}, "
            f"timeout={dep['container_timeout_minutes']} min)"
        )

    cheapest = pick_cheapest_gpu(config["min_vram_gb"])
    if cheapest:
        print(
            f"cheapest GPU meeting min_vram={config['min_vram_gb']} GB: "
            f"{cheapest['gpu']} ({cheapest['vram_gb']} GB, "
            f"${cheapest['price_usd_per_hour']:.2f}/h)"
        )
    else:
        print(f"cheapest GPU: NONE meets min_vram={config['min_vram_gb']} GB")
        errors.append("no GPU in market table meets min_vram_gb")

    if errors or job_errors:
        return 1
    print("check: PASSED")
    return 0


def cmd_dry_run(config_path: Path | None) -> int:
    config, source = load_config(config_path)
    errors = validate_config(config)
    if errors:
        print("config invalid:")
        for e in errors:
            print(f"  - {e}")
        return 1

    cheapest = pick_cheapest_gpu(config["min_vram_gb"])
    print("Nosana Cost Guard — dry run (nothing will be stopped)")
    print(f"config: {source}")
    print(
        f"rules: idle > {config['idle_minutes']} min → STOP; "
        f"spend > ${config['max_spend_usd']:.2f} → STOP; "
        f"strategy must be SIMPLE; replicas must be 1"
    )
    if cheapest:
        print(
            f"cheapest GPU meeting min_vram={config['min_vram_gb']} GB: "
            f"{cheapest['gpu']} (${cheapest['price_usd_per_hour']:.2f}/h)"
        )
    print()

    log_entries: list[dict] = []
    total_cost = 0.0
    stopped = 0
    for dep in sample_deployments():
        decision, reasons, cost = evaluate(dep, config)
        total_cost += cost
        if decision == "STOP":
            stopped += 1
        reason_text = "; ".join(reasons) if reasons else "within limits"
        print(
            f"[{decision}] {dep['id']} — {dep['gpu']}, "
            f"runtime {dep['runtime_minutes']} min, "
            f"idle {dep['idle_minutes']} min, "
            f"{dep['requests']} requests, {dep['strategy']}, "
            f"est. cost ${cost:.2f} — {reason_text}"
        )
        log_entries.append(
            {
                "event": "dry-run-evaluate",
                "deployment_id": dep["id"],
                "decision": decision,
                "reason": reason_text,
                "cost_usd_estimate": cost,
                "dry_run": True,
            }
        )

    log_path = HERE / str(config.get("audit_log", "audit.log.jsonl"))
    append_audit_log(log_path, log_entries)
    print()
    print(
        f"sample total est. cost: ${total_cost:.2f} "
        f"({stopped}/{len(log_entries)} would be STOPPED)"
    )
    print(f"audit log written: {log_path} ({len(log_entries)} entries, dry_run=true)")
    print("verify it with: python3 verify.py")
    return 0


def cmd_live() -> int:
    print("live mode is NOT implemented yet.")
    print()
    print("To stop a real Nosana deployment the guard needs:")
    print("  1. A Nosana Deploy account and a real deployment ID")
    print("  2. A Nosana API key (nos_...) — never commit one to this repo")
    print("  3. The current Nosana API/CLI surface verified by hand first")
    print()
    print("Next step (TODO): run the 30-minute test in BENCHMARK.md,")
    print("record the real cost, then implement --live behind a")
    print("$2 spend cap and a 30-minute timeout.")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nosana Cost Guard")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate against sample deployments; stop nothing")
    parser.add_argument("--check", action="store_true",
                        help="Validate config and job-definition.json")
    parser.add_argument("--live", action="store_true",
                        help="Stop real deployments (not implemented yet)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to a config JSON file")
    args = parser.parse_args(argv)

    config_path = Path(args.config) if args.config else None
    if args.live:
        return cmd_live()
    if args.check:
        return cmd_check(config_path)
    if args.dry_run:
        return cmd_dry_run(config_path)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
