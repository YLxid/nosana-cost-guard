# Nosana Cost Guard

A solo-built budget guard for Nosana deployments — a small CLI and a
single-page dashboard that stops idle GPU deployments before they burn
through your credits.

Built for the **Decentralize AI Hackathon by HackerNoon** (Round 2,
Nov 2026 – Feb 2027), in the *decentralized GPU orchestration / AI
deployment tooling* category.

> **Status: early prototype, not yet run on Nosana.** The CLI works
> locally in `--dry-run` and `--check` mode. No live Nosana deployment,
> no real cost measurement, and no Arweave upload has been done yet.
> See [Limitations](#limitations) and [`BENCHMARK.md`](BENCHMARK.md).

## The problem

The Nosana claim page itself warns about it: a deployment left on the
default **Infinite** strategy keeps running until your credits run out.
With an NVIDIA RTX 5090 at about $0.48/hour, that is roughly $350/month
if left running 24/7 — and the $70 in hackathon credits would be gone
in about 140–145 hours. An RTX 4090 at about $0.40/hour burns the same
$70 in about 175 hours.

Most of that time is not inference. It is idle time: a model pulled,
a few prompts tested, and then the container left running while the
builder does something else.

Cost Guard exists to make the safe configuration the default one:

- **SIMPLE** deployment strategy (not Infinite)
- **Replica count: 1**
- **An explicit container timeout** (30–60 minutes for test runs)
- **Auto-stop** when a deployment has been idle longer than
  `idle_minutes`, or when its spend passes `max_spend_usd`
- **Cheapest GPU market** that still meets a minimum VRAM requirement
- **A hash-chained audit log** of every decision, so the cost story
  can be checked afterwards instead of taken on trust

## What it is — and what it is not

- It **is** open-source deployment tooling for solo builders on a
  $70 credit budget: a rule engine, an audit log, and a dashboard.
- It **is not** a meta-agent that deploys other agents, and it is not
  a general-purpose orchestrator. It guards one deployment at a time,
  with explicit, inspectable rules.
- It **does not** train or fine-tune a model. The test workload is
  plain Ollama inference (`qwen3:8b`) so the guard itself can be
  measured without a training bill.

## Architecture

```
┌─────────────────┐      ┌──────────────────────┐
│  Nosana         │      │  guard.py (stdlib    │
│  deployment     │◄─────│  Python, no heavy    │
│  (Ollama        │      │  dependencies)       │
│   qwen3:8b)     │      │                      │
└─────────────────┘      │  • load config       │
        ▲                │  • pick cheapest GPU │
        │                │    meeting min VRAM  │
        │                │  • evaluate rules:   │
        │                │    idle / spend /    │
        │                │    strategy / replica│
        │                │  • append hash-      │
        │                │    chained audit log │
        └────────────────└──────────┬───────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ audit.log.jsonl               │
                    │ (JSONL, SHA-256 hash chain)   │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ verify.py  →  VERIFIED/FAILED│
                    │ dashboard/index.html          │
                    │ (static page, reads the log)  │
                    └───────────────────────────────┘

Planned (not implemented yet):
  audit log manifest → Arweave (permanent, verifiable record)
```

## Quick start

Requirements: Python 3.10+ only. No third-party packages.

```bash
git clone https://github.com/YLxid/nosana-cost-guard.git
cd nosana-cost-guard

# 1. Check the configuration and the job definition — no credentials needed
python3 guard.py --check

# 2. Simulate the guard against sample deployments — nothing is stopped
python3 guard.py --dry-run

# 3. Verify the audit log's hash chain
python3 verify.py
# expected: VERIFIED

# 4. View the dashboard (served locally so it can fetch the log)
python3 -m http.server 8000
# open http://localhost:8000/dashboard/
```

## Configuration

Copy `config.example.json` to `config.json` and edit it. Never commit
real credentials — `config.json` is git-ignored, and this project
needs no API key at all in dry-run mode.

```json
{
  "idle_minutes": 10,
  "max_spend_usd": 2.0,
  "enforce_simple": true,
  "replica_count": 1,
  "min_vram_gb": 24,
  "container_timeout_minutes": 45,
  "credit_budget_usd": 70.0,
  "gpu_price_usd_per_hour": 0.40
}
```

| Key | Meaning |
|---|---|
| `idle_minutes` | Stop a deployment idle longer than this. |
| `max_spend_usd` | Stop a deployment whose estimated spend passes this. |
| `enforce_simple` | Require SIMPLE strategy; flag Infinite as a violation. |
| `replica_count` | Must be 1 for test runs. |
| `min_vram_gb` | Minimum VRAM when picking the cheapest GPU market. `qwen3:8b` needs ~24 GB. |
| `container_timeout_minutes` | Timeout to set on the deployment (30–60 min for tests). |
| `credit_budget_usd` | Total budget the dashboard shows remaining against ($70). |
| `gpu_price_usd_per_hour` | Price used for estimates. Check the live Nosana dashboard — prices change. |

### Cheapest-GPU picker

The picker uses a small built-in market table (prices as reported
Nov 2026, **verify on the dashboard before deploying**):

| GPU | VRAM | $/hour |
|---|---|---|
| RTX 3060 | 12 GB | 0.048 |
| RTX 3080 | 10 GB | 0.096 |
| RTX 5070 | 12 GB | 0.15 |
| RTX 4090 | 24 GB | 0.40 |
| RTX 5090 | 32 GB | 0.48–0.50 |
| H100 | 80 GB | 1.50 |

With `min_vram_gb: 24`, the cheapest qualifying GPU is the RTX 4090
at $0.40/hour. That is the test workload in
[`job-definition.json`](job-definition.json).

## Test workload

`job-definition.json` is the Nosana job used to test the guard:
Ollama serving `qwen3:8b` (about 24 GB VRAM), GPU enabled, SIMPLE
strategy, 1 replica, 45-minute container timeout.

Test scenario (recorded in `BENCHMARK.md`):

1. Start the deployment, run 10 prompts against it.
2. Leave it idle for 10 minutes.
3. Cost Guard must auto-stop it and write the decision to the audit log.
4. Compare the cost with the guard against the cost of leaving the
   same deployment on the default Infinite / 6-hour timeout.

**This run has not been done yet.** The benchmark file contains the
honest calculation for the scenario and a TODO for the measured
numbers after the first real run.

## Audit log and verification

Every decision is appended to `audit.log.jsonl`, one JSON object per
line, hash-chained:

```json
{"seq": 1, "timestamp": "...", "event": "evaluate", "deployment_id": "ollama-test-01",
 "decision": "STOP", "reason": "idle 12 min > 10 min limit",
 "cost_usd_estimate": 0.23, "prev_hash": "0000...0000",
 "hash": "a1b2..."}
```

Each entry's `hash` is SHA-256 over the canonical JSON of the entry
(without `hash`) plus `prev_hash`. The first entry uses 64 zeroes as
`prev_hash`.

```bash
python3 verify.py                 # verify audit.log.jsonl
python3 verify.py --file other.jsonl
```

`verify.py` recomputes every hash and the chain order, and prints
`VERIFIED` or `FAILED` with the first failing entry. Tampering with
any line — changing a cost, a decision, or a timestamp — breaks the
chain.

**Arweave (planned, not done):** the audit-log manifest (SHA-256 of
the log file plus the log itself for small logs) is intended to be
uploaded to Arweave so the record is permanent and publicly
checkable. No upload has been made, no Arweave transaction ID exists
for this project, and Arweave credits are not assumed to be free —
the FAQ says Arweave credits go to winning or qualifying projects,
not automatically to every participant.

## Live mode

Live mode (actually stopping a Nosana deployment via the Nosana API
or CLI) is **not implemented yet**. It is a TODO, deliberately:

- It needs a Nosana account, a deployment ID, and an API key
  (`nos_...`), none of which should ever be committed to this repo.
- The Nosana API surface changes; the first live test must be done
  against the current dashboard/CLI, with a 30-minute timeout and a
  $2 spend cap, and the measured result recorded in `BENCHMARK.md`.

`guard.py --live` today refuses to run and explains what is missing,
instead of pretending to stop something.

## Roadmap

- [x] Rule engine + dry-run + config validation (this repo)
- [x] Hash-chained audit log + verifier
- [x] Static dashboard + benchmark template
- [ ] First live test run (30 min, Ollama `qwen3:8b`, RTX 4090) —
      record real cost in `BENCHMARK.md`
- [ ] Live mode: stop a real deployment via Nosana API/CLI
- [ ] Live GPU-market lookup (replace the built-in price table)
- [ ] Arweave upload of the audit-log manifest + TX in the README
- [ ] HackerNoon write-up documenting the build and the measured
      savings (required for a full hackathon submission)

## Limitations

- **No live run yet.** All cost numbers in `BENCHMARK.md` are
  calculations from published prices, not measurements.
- **Prices change.** The $0.40 (4090) and $0.48–0.50 (5090) figures
  are from Nov 2026 sources; check the Nosana dashboard at deploy
  time. There is also an unverified community claim that credits
  only apply in the PREMIUM market — that has not been confirmed
  from official Nosana documentation.
- **The built-in GPU price table is a snapshot**, not a live market
  feed. The picker is correct only as far as the table is.
- **Idle detection in dry-run mode uses sample data**, not live
  request logs from a Nosana endpoint.
- **Orchestration is a crowded category** (e.g. AgentForge won
  Nosana Builders' Challenge #4 with a meta-agent orchestrator).
  This project's differentiator is deliberately narrow: a budget
  guard for solo builders on $70 of credits, with a verifiable
  audit log and measured savings — not a general orchestrator.
- **Arweave upload is planned, not done.** Nothing in this repo
  should be read as claiming an Arweave transaction exists.

## License

MIT — see [`LICENSE`](LICENSE).
