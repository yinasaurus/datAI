# Scenario v2: development draft

This is a development-only benchmark revision. The original `data/scenarios/`
files remain the legacy benchmark and are not overwritten. No v2 held-out set
has been generated or frozen. Do not combine scores from the two versions.

## Design

There are 24 two-day scenarios: 2 mechanisms × 3 group sizes (2, 3, 5) ×
2 proposed severity labels × 2 budget levels. Within each budget pair, likes,
restrictions, names, and order remain identical; only budgets change. Restriction
owners vary across group sizes/severity cases rather than always excluding Amy.
These are structured fixtures, not 24 independent samples of real travellers.

- `direct_recoverable`: someone likes a forbidden category plus an attainable
  alternative. Mild has one direct forbidden preference; strong has two. Nobody
  is restricted to forbidden preferences only. Tight group minimum is SGD 23;
  loose is SGD 120. Individual budgets increase by role index.
- `budget_pressure`: no temple prohibition. Tight group minimum is SGD 7; loose
  is SGD 30. Every person has culture as one possible category, so low budgets
  need not leave anyone at zero. Strong increases two roles from two likes to
  three and adds a no-early-mornings restriction. These labels describe intended
  conditions, not an established empirical ranking of difficulty.

The low budgets are synthetic attraction/activity budgets for the modelled
itinerary only. They exclude accommodation, transport fares, flights, and a full
meal allowance. They are not estimates of a complete Kyoto holiday's cost.

## Achievability audit

`development_audit.json` stores a concrete plan and the production checker report
for every scenario. Each plan has exactly two days, two distinct places per day,
no repeats, full hard-limit satisfaction, and no feasibility violations.

The audit enumerates ordered two-place day schedules and pairs disjoint days
within budget. It records a lower bound on the best minimum friend satisfaction.
An independent optimistic upper bound uses all individually affordable,
visit-duration-compatible places after applying every hard limit. It ignores
joint scheduling and combined costs, so it cannot underestimate the true optimum.
When a witness attains this bound, the maximum minimum satisfaction is proven
under the repository's current model, even though the witness search uses four
visits. Otherwise the output is an interval, not an optimality claim. The audit
proves only the minimum satisfaction objective, not mean satisfaction or cost.

Current bounds coincide for all 24 cases:

| Mechanism/condition | Scenarios | Maximum minimum satisfaction |
| --- | ---: | ---: |
| Direct recoverable, all conditions | 12 | 0.5 |
| Budget pressure, mild tight | 3 | 0.5 |
| Budget pressure, strong tight | 3 | 1/3 |
| Budget pressure, loose | 6 | 1.0 |

These values are reference ceilings, not observed LLM performance. Broad tags
and cheap multi-tag places make some cases easy. Tight cases can make individual
liked categories unaffordable; this is not necessarily a genuine choice between
two equally attainable group compromises. The draft fixes the universal zero
floor but does not establish that negotiation is necessary or beneficial.

## Commands

Validate the draft:

```bash
.venv/bin/python -m scripts.validate_scenarios --scenarios data/scenarios_v2/dev
```

Reproduce scenarios and witnesses in a fresh folder (existing outputs are refused):

```bash
.venv/bin/python -m scripts.generate_dev_v2 --output /tmp/tripbot-v2-review
```

Run a model on one fixture, if desired (uses Gemini and may incur usage):

```bash
.venv/bin/python -m scripts.run_setup_a --setup A --scenario data/scenarios_v2/dev/v2_dev_001.json
```

Review this development design before defining new held-out scenarios. Keep
witnesses, ceilings, and audit metadata out of model prompts in the final study.
