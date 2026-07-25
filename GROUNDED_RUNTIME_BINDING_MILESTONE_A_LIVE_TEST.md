# Grounded Runtime Binding — Milestone A live-shadow test

> This is the remaining Milestone A test. The observer is additive, learner-invisible, and off by default.
> Do not start Milestone B until the resulting strict report passes.

## Controls

- `AZALEA_T6_SUBSTRATE_SHADOW=off|observe` — master rollback switch; default `off`.
- `AZALEA_T6_SUBSTRATE_SHADOW_PATH=<path>` — append-only JSONL destination.
- `AZALEA_T6_SUBSTRATE_SHADOW_SAMPLE_RATE=0..1` — deterministic substrate-comparison fraction. Every
  FormulaSpec execution is still counted for volume coverage.
- `AZALEA_T6_SUBSTRATE_SHADOW_SLUGS=a,b,c` — optional comparison allowlist. Empty means all eligible rows.

No setting changes routing or learner-visible output. A substantive mismatch records
`quarantine_required=true`; an executor exception is recorded separately. Turning the master switch to `off`
is the rollback.

## Recommended first run

Use a new telemetry file so earlier test data cannot contaminate the result:

```powershell
$env:AZALEA_T6_SUBSTRATE_SHADOW='observe'
$env:AZALEA_T6_SUBSTRATE_SHADOW_SAMPLE_RATE='1'
$env:AZALEA_T6_SUBSTRATE_SHADOW_PATH='logs/t6_substrate_shadow.jsonl'
```

Run the agreed controlled study-path regenerations. Then:

```powershell
.\venv\Scripts\python.exe scripts\summarize_t6_shadow.py logs/t6_substrate_shadow.jsonl
.\venv\Scripts\python.exe scripts\report_t6_milestone_a.py --output reports/t6_milestone_a_v1.json
```

## Acceptance

- At least 100 FormulaSpec executions across at least 10 distinct eligible slugs.
- Both eligible and blocked rows appear, proving the traffic denominator is not eligibility-filtered.
- Zero execution mismatches.
- Zero substrate exceptions.
- Zero `quarantine_required` events.
- Comparison p95 latency below 10 ms.
- The consolidated Milestone A decision becomes `pass`.

If any correctness condition fails, set the master switch to `off`, retain the JSONL evidence, and do not
advance. Low volume or insufficient slug diversity means continue the shadow test; it is not a correctness
failure.
