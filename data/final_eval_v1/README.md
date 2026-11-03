# Final Kyoto evaluation v1

This is an unseen-profile held-out benchmark, separate from all development batches. It contains 20 feasible scenarios, organised as 10 families × 2 budget variants. Family members are dependent; use the family-cluster analysis, not a 20-independent-scenario confidence interval.

| Factor | Scenarios |
| --- | ---: |
| Straightforward | 8 |
| Conflicting but feasible | 8 |
| Highly constrained but feasible | 4 |
| 2 friends | 8 |
| 3 friends | 6 |
| 5 friends | 6 |
| Tight / loose budget variants | 10 / 10 |
| One / two / three days | 4 / 14 / 2 |
| Intentionally infeasible | 0 |

`heldout/*.json` are the only planner scenario inputs. `manifest.json` supplies dataset/family/template identifiers, difficulty, hashes and checker settings. `witnesses.json` holds checker-only existence proofs, including positive minimum satisfaction for every scenario. Do not give the planner witnesses or use final model outputs for tuning.

Generation: `scripts/generate_final_scenarios.py` (deterministic, no LLM, refuses overwrite). It checks new preference/day templates against existing scenario and saved experiment inputs. Ten new templates were constructed from the existing catalogue and restrictions, not sampled from users. Each friend shares culture as an attainable interest, while other interests may conflict with restrictions; this avoids forced-zero minimum utility but limits population generalisation. Budget labels are relative within template pairs, not proven optimal-budget thresholds. The three-day family requires six distinct visits; exact days and two visits/day remain the existing checker rules.

All 20 checker witnesses pass feasibility and all hard limits. Witnesses are not fairness optima. No final model outputs have been generated. Keep this dataset unchanged after the code freeze. See [the final protocol](../../FINAL_EVALUATION_PROTOCOL.md) for commands, metrics, inference and limitations.
