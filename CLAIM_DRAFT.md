# Claim draft — Nosana $70 credits

Form: https://decentralizeai.tech/claim/nosana
Do NOT submit until: (1) the GitHub repo exists at the URL below,
(2) Taylor has filled in the personal fields, (3) the first live
test plan in BENCHMARK.md is understood. This file is a draft only —
nothing has been submitted.

## Copy-paste fields

### Project Name

```
Nosana Cost Guard
```

### Proposal Description (minimum 150 characters)

```
Nosana Cost Guard is a solo-built budget guard for Nosana deployments: a CLI and single-page dashboard that enforces SIMPLE strategy, replica 1, and a container timeout, auto-stops idle deployments, picks the cheapest GPU market meeting a minimum VRAM, and writes a hash-chained audit log of every start/stop and cost to Arweave. It solves the exact problem on the claim page where Infinite deployments burn $70 in credits, and it is built as open-source deployment tooling for the Decentralize AI Hackathon.
```

- **Character count: 508** (minimum required: 150) ✅

### GitHub Repository URL

```
https://github.com/vannyfriskaa-blip/nosana-cost-guard
```

- Status: **TODO — repo does not exist yet.** Create it as a public
  repo from this local folder first, then paste the URL. Do not
  submit the form with a repo URL that does not exist yet.

### Model / Workload Details (minimum 20 characters)

```
Ollama qwen3:8b inference, 24 GB VRAM, RTX 4090, SIMPLE, replica 1, 1-2 h test runs with auto-stop on idle.
```

- **Character count: 107** (minimum required: 20) ✅

### Do you plan to deploy or test your project on Nosana?

```
Yes
```

### Team Information

- Team: solo — **Taylor (1 person)**. One claim per team; Taylor is
  the single representative.
- Team Members: `Taylor` (add full name as Taylor wishes it to appear)

### Contact Information — TODO, Taylor to fill in

- [ ] Email Address: ____________________
- [ ] Phone Number: ____________________
- [ ] Country: ____________________ (Indonesia)

### Agreement

- [ ] "I confirm this submission is from one representative per team
      and that all information provided is accurate."

## What happens after submitting

Per the claim page: approval is by manual review, and approved
participants receive the Nosana credit access instructions **by
email**. There is no instant on-page grant. Watch the email address
used in the form.

## Honesty notes for the form

- The repo at claim time will contain: README, `guard.py`
  (dry-run + check, live mode not implemented), `verify.py`,
  `job-definition.json`, `config.example.json`, `BENCHMARK.md`
  (calculated savings + TODO for measured results), and the static
  dashboard. That is a real, non-empty repo — not a placeholder.
- The proposal says the audit log is written "to Arweave". In this
  repo that is the **planned** destination for the log manifest;
  no Arweave upload has been done yet and no transaction ID exists.
  The README and BENCHMARK.md say this plainly. If the claim form
  has a free-text field for status, add: "Arweave upload of the
  audit-log manifest is planned after the first live run; the local
  hash-chained log and verifier are implemented now."
- Do not claim a live Nosana deployment or measured savings in the
  form. The first live test (30 minutes, RTX 4090) is a TODO in
  BENCHMARK.md.
