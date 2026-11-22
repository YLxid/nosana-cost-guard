# Benchmark — Nosana Cost Guard

## Status

**No real run has been done yet.** Everything in the "Calculated"
section below is arithmetic from published prices, not a measurement.
The "Measured" section is a TODO to fill in after the first live
test run. Do not quote the calculated numbers as if they were
measured results.

## Prices used (verify on the Nosana dashboard before deploying)

| GPU | $/hour | Source |
|---|---|---|
| RTX 4090 | 0.40 | SolanaCompass, Nov 2026 |
| RTX 5090 | 0.48–0.50 | Claim page ($0.48) / SolanaCompass ($0.50), Nov 2026 |
| RTX 3060 | 0.048 | SolanaCompass, Nov 2026 |

Prices change, and there is an **unverified** community claim that
credits only apply in the PREMIUM market. Check the dashboard on the
day of the run and record the actual price paid.

$70 of credits buys, at these prices:

- RTX 4090 @ $0.40/h → ~175 hours
- RTX 5090 @ $0.48–0.50/h → ~140–145 hours

## Test scenario (the run to be measured)

1. Start the deployment from [`job-definition.json`](job-definition.json):
   Ollama `qwen3:8b`, RTX 4090, SIMPLE, replica 1, 45-minute timeout.
2. Run 10 prompts against the Ollama endpoint.
3. Leave the deployment idle for 10 minutes.
4. Cost Guard must auto-stop it and write the decision to
   `audit.log.jsonl`.
5. Record: start time, first-prompt time, last-prompt time, stop
   time, total runtime, and the cost shown by Nosana.

## Calculated — what the guard should save (not measured)

Assumption for the calculation only: 10 prompts take about 20 minutes
of active time (model pull + inference). This is an assumption, not a
measurement — the real active time goes in the Measured section.

| Scenario | Runtime | RTX 4090 @ $0.40/h | RTX 5090 @ $0.48/h |
|---|---|---|---|
| **With guard:** 20 min active + 10 min idle grace, then auto-stop | 30 min (0.5 h) | **$0.20** | **$0.24** |
| **Without guard:** default 6-hour container timeout | 6 h | $2.40 | $2.88 |
| **Without guard:** left running 24 hours | 24 h | $9.60 | $11.52 |
| **Without guard:** left until the $70 credit is gone | ~175 h (4090) / ~146 h (5090) | $70.00 | $70.00 |

Savings in the test scenario (6-hour timeout case):

- RTX 4090: $2.40 − $0.20 = **$2.20 saved (92%)**
- RTX 5090: $2.88 − $0.24 = **$2.64 saved (92%)**

The percentage is the point, not the dollars: in a 30-minute test
the guard saves a few dollars; in a forgotten deployment it saves
the whole $70.

### Dry-run sample (simulated, not a real run)

`python3 guard.py --dry-run` evaluates three sample deployments:

| Deployment | Runtime | Idle | Decision | Est. cost |
|---|---|---|---|---|
| ollama-test-01 (4090) | 35 min | 12 min | STOP (idle) | $0.23 |
| ollama-test-02 (4090) | 15 min | 3 min | KEEP | $0.10 |
| ollama-test-03 (5090, Infinite) | 300 min | 0 min | STOP (spend + strategy) | $2.40 |
| **Total (sample)** | | | **2 of 3 stopped** | **$2.73** |

This only proves the rule engine and the audit log work. It proves
nothing about real Nosana costs.

## Measured — TODO after the first live run

Fill this in after the first 30-minute live test. Do not fill it in
beforehand.

| Field | Value |
|---|---|
| Date of run | TODO |
| GPU actually used + price actually paid ($/h) | TODO |
| Model | qwen3:8b (planned) |
| Deployment start (UTC) | TODO |
| First prompt / last prompt (UTC) | TODO |
| Auto-stop time (UTC) | TODO |
| Total runtime (minutes) | TODO |
| Cost shown by Nosana | TODO |
| Cost with guard vs. 6-hour timeout, same GPU | TODO |
| Audit log entry seq / hash (first 12 chars) | TODO |
| Dashboard screenshot | TODO |
| What went wrong / what surprised us | TODO |

## How to reproduce

```bash
python3 guard.py --check
python3 guard.py --dry-run
python3 verify.py
```

Then, for the live run: create the deployment from
`job-definition.json` (or the equivalent dashboard template) with a
30–45 minute timeout, run the 10 prompts, wait 10 minutes idle,
confirm the guard stops it, and record the numbers above.
