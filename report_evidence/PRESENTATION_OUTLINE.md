# IS469 presentation outline — frozen research evidence

Prepared 4 November 2026. An outline of objectives, evidence and visuals only; not a spoken script. Use [RESEARCH_FINDINGS.md](RESEARCH_FINDINGS.md) for definitions, full tables, uncertainty and evidence links. Confirm the course’s actual slide/time limit and condense as needed; no numeric limit was available in the supplied requirements. Students must explain their own parts unaided, without a script or notes, and personally vet all material.

| Slide | Objective | Key evidence to show | Suggested visual and accuracy constraint |
| --- | --- | --- | --- |
| 1. Problem and research questions | Establish why group travel is a constraint and preference conflict problem | Verification/delivery, mediation/fairness-cost, guards/functionality are three separate questions | One small example with conflicting budgets/interests; label any schematic example as illustrative, not an extra evaluated scenario |
| 2. Experimental architectures | Explain A/B/C precisely and identify C0/C2 as C ablations | A one call; B same initial prompt + up to 3 repairs; C0 n proposals + mediator; C2 3n proposals + mediator; same repair loop | Four compact flows with shared checker/data highlighted; distinct model calls, same underlying model; C2 uses previous-round snapshots |
| 3. Frozen evaluation design | Establish what conclusions the evidence can support | Planning 20 scenarios/10 families × 3 runs × 4 conditions = 240; independent witnesses; method7/prompt8; separate security freeze | Two-lane planning/security design diagram, short commit hashes with full hashes in appendix; mention unequal compute and synthetic profiles |
| 4. RQ1: reliable itinerary delivery | Show observed benefit of verification-and-assisted-repair | A48/60=80%; B/C0/C2 each60/60; B−A +20 pp, 95% family interval [5, 35]; delivered min +0.1417 [0.0333,0.2583] | Delivery bars with exact counts plus contrast annotation; do not apply contrast CIs to individual bars |
| 5. Why repair helped | Explain an actual failure and actual correction | A family02 cost 29 > budgets 25/26; B family02 r1 initial same violation, one repair to cost 21, minimum utility 1; A family03 day 2 only 1 activity | Redacted planning trace excerpt: initial check → feedback → revision → passing check; cite exact job IDs; no claim every initial output matches |
| 6. RQ2: fairness versus computation | Separate uncertain quality gain from measured computational increase | C0−B delivered min +0.0417 [−0.0502,0.1417]; C2−C0 ≈0 [−0.0500,0.0500]; calls1/1.2/4.5/10.95; seconds1.523/1.824/6.909/17.058 | Paired minimum-utility forest plot beside calls/latency small multiples; note failed-plan zeroing, 10 families, no general superiority |
| 7. Security method and trust boundary | Explain matched inputs and what was actually tested | Six payloads×3×attack/baseline=36 generations;18pairs; same candidate replayed guards off/on; cap30 | Untrusted chat/place text → model candidate → simulated reply/tool/booking gates; explicitly label not a live Telegram exploit or tool execution |
| 8. RQ3: observed guard prevention | Distinguish model nonattempts from actual prevented attempts | All-target 3/18 off→0/18 on; canary cohort 3/6→0/6; one `a_10` payload repeated 3 times; prevention 3/3 eligible;15/18 nonattempts | Paired disclosure count bars plus safe public a_10 excerpt “[CANARY REDACTED]”; baseline has no disclosure; also over cap so no isolated canary-rule effect |
| 9. Guard functionality and blind spots | Show adverse findings rather than only successful blocks | Safe allow 21/24=87.5%;false block 3/24=12.5%;unsafe diagnostics 15/15 blocked;one benign quote repeated 3 times;6 under-cap incomplete replies allowed | Safe-action stacked bar and two annotated cards: benign description blocked / sparse plan allowed; distinguish reply checks from full feasibility at booking |
| 10. Conclusions, limits, future directions | Answer all three questions within evidence boundaries | Verification helped here; mediation fairness gain not established at extra cost; guard enforcement bounded with false blocks/coverage gaps | Three concise findings with matching limitation; small benchmark, provider alias, no actual exploit testing. Future work labelled proposed, not completed |

## Optional appendix slides (keep outside the main narrative if space is limited)

- Full architecture quality and efficiency tables, including hard fraction, raw/delivered satisfaction, Jain and gap.
- All three prespecified paired contrasts; bootstrap uses 10 family clusters, 1,000 draws, seed 42; repetitions are not independent scenarios. Token contrasts use19 complete scenarios where usage is unknown.
- Matched security endpoint table: config 0/0/0/18; booking 0/0/0/18; canary 3/0/0/15; cap 0/6/12/0 (attack-only/baseline-only/both/neither), each denominator 18.
- Development versus held-out: development0/12 intended attempts, heldout3/18; different payload sets, not a performance trend. Baselines all over cap; model-safe FPR unavailable.
- Operations: planning 240/240,2 recovered 503 requests,0 terminal errors; security 36/36,36 calls,160,182 input / 9,945 output tokens,1.559 s mean,0 retries/errors.
- Frozen revisions, source manifests, evidence-to-claim IDs E1–E14 and public artifact paths. Do not display private raw traces or synthetic canary values.
- Contributions, integration and reproducibility: actual named member contributions reviewed individually; repository access and environment instructions. Do not infer contributions from commit volume.

## Chart source and preparation checklist

Use the exact chart specifications in [findings](RESEARCH_FINDINGS.md#chart-specifications-for-the-report-and-slides), with [planning conditions](../results/kyoto-final-v1-01/analysis/conditions.csv), [paired CIs](../results/kyoto-final-v1-01/analysis/pairs.csv), [held-out targets](../results/security-v2-final-review-01/heldout_targets.csv) and [safe-action controls](../results/security-v2-controls-01/safe_actions.csv). No new model calls or recomputation of experimental outcomes is required.

Before presenting: verify each plotted value/denominator against its source; show CIs only for archived contrasts; mark fixed/repeated cases; use legible axes/accessible colours; assign sections to actual contributors; rehearse explaining mechanisms and limitations independently. Retain both false blocks and allowed-incomplete outputs. Never claim general multi-agent superiority, general injection resistance, or actual Telegram exploit prevention.

## Report-compatible closing findings (not a script)

- Verification-and-repair improved benchmark delivery by20 percentage points; archived family-aware 95% interval[5, 35].
- Mediation’s delivered-minimum gains were uncertain; added negotiation increased calls/latency without a demonstrated quality benefit here.
- Guards prevented all 3 observed off-authorised target disclosures from one repeated payload, but falsely blocked 3/24 safe fixed actions and allowed 6 incomplete under-cap replies.

Planning revision: `46bf8d1e3c65ea8144e339eeb0f02d1577fae6d1`. Security revision: `0cd756b988f599897dc3b19d3652594587a1be44`. Evaluation artifacts stay frozen. The main report needs group-written motivation/related work, contribution statements and personal verification beyond this evidence outline.
