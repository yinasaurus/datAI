# Synthetic budget-choice benchmark: development draft

All places, interests, costs, durations, and opening hours in this directory are
fictional. Costs are abstract per-person budget units, not SGD or real travel
prices. Every place has `verified: false` and a `synthetic:` source. This data is
separate from Kyoto and must be reported as a separate experiment.

## What this tests

There are eight scenarios in three worlds, for 2, 3, and 5 friends. The worlds
have their own places, vocabulary, travel table, and configuration. Scenarios
retain the existing profile/plan schemas and run through the existing A/B/C
planners and checker without special scoring rules.

Each friend likes two unique categories, a and b:

- Their private place covers both and costs 6.
- A shared place covers category a for every friend and costs 3.
- Four neutral free places cover no friend's likes and allow a trip to meet
  its minimum activity requirement without requiring extra paid attractions.

All visits last 60 minutes, open 10:00–18:00, and require five minutes of travel.
Trips have exactly two days, at least two visits per day, and no repeated places.
Timing is deliberately generous: this isolates budget allocation rather than
pretending to study scheduling difficulty. Neutral fillers and the shared option
make these transparent diagnostic cases, not realistic tourism recommendations.

In constrained conditions every friend can be fully satisfied in a valid group
itinerary individually, but all friends cannot be fully satisfied simultaneously.
There are multiple feasible satisfaction outcomes. The control budget allows
full satisfaction for all friends. No output is assumed to require negotiation;
A or B may solve these cases equally well or more cheaply.

## Proven reference results

The development audit enumerates every subset with at least four visits. With
at most ten available places and identical hours/durations, every such subset
fits in a canonical two-day schedule. It checks each affordable subset using
the production checker. Different orders, longer visits, or later starts cannot
improve tag coverage, so this enumeration establishes the optimum over all valid
plans for this world, not just a sample of generated schedules.

Every b category requires its owner's private place. Therefore full satisfaction
for everyone costs at least `6 × group size`; this bound is attainable with free
fillers where needed. With less money, optimal minimum satisfaction is 0.5.
Among plans achieving that minimum, the audit also finds the maximum mean.

| Friends | Budget per person | Best minimum | Best mean at that minimum | Condition |
| --- | ---: | ---: | ---: | --- |
| 2 | 6 | 0.5 | 0.5 | Constrained |
| 2 | 12 | 1 | 1 | Full-satisfaction control |
| 3 | 6 | 0.5 | 0.5 | More constrained |
| 3 | 12 | 0.5 | 2/3 | Constrained |
| 3 | 18 | 1 | 1 | Full-satisfaction control |
| 5 | 12 | 0.5 | 0.6 | More constrained |
| 5 | 24 | 0.5 | 0.8 | Constrained |
| 5 | 30 | 1 | 1 | Full-satisfaction control |

At budgets 6, 12, and 24 for groups of 2, 3, and 5 respectively, a zero-minimum
plan can achieve the same mean as the best balanced plan. For three friends,
`(1, 1, 0)` and `(1, 0.5, 0.5)` both average 2/3. This makes minimum satisfaction
informative even when mean satisfaction is tied. Example plans and per-friend
individual-achievability witnesses are in `development_audit.json`.

The existing `conflict` field labels lower constrained caps as strong and the
other caps as mild; `budget` distinguishes tight from the full-satisfaction loose
control. Analyse the explicit numeric caps and conditions. These are not the
same difficulty definitions as the Kyoto scenarios.

## Run from the repository root

Validate one world without any model request:

```bash
.venv/bin/python -m scripts.validate_scenarios --config data/synthetic_v1/n3/config.yaml --scenarios data/synthetic_v1/n3/dev
```

Reproduce fixtures and audit in a fresh folder (existing folders are refused):

```bash
.venv/bin/python -m scripts.generate_synthetic_dev --output /tmp/tripbot-synthetic-review
```

Run one planner (requires the Gemini key and can incur usage):

```bash
.venv/bin/python -m scripts.run_setup_a --setup A --config data/synthetic_v1/n3/config.yaml --scenario data/synthetic_v1/n3/dev/syn_n3_budget12.json
```

Use B or C with the same matching config/scenario pair. The ordinary bot remains
configured for Kyoto; these configs are intended for offline experiments only.
Keep audits and optimal scores out of model prompts. No live model calls were
used to construct or audit this dataset.

## Limits and next decisions

These eight cases are hand-designed development diagnostics, not eight independent
samples from a real traveller population. They share one simple mechanism and
can be solved analytically. No held-out synthetic set has been generated or
frozen. Do not claim statistical generalisation from these cases or pool them
with Kyoto scores. Before final evaluation, agree the objective communicated to
all setups and a held-out design; avoid tailoring cases to make C win.
