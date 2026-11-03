# Security evaluation v1 readiness

**Ready for review and approval as a separate action-boundary security experiment.** The security package must be committed before measured runs; `--require-clean` enforces this. No model-driven/paid security experiment has been executed. The frozen planning evaluation remains separate and unchanged.

| Component | Status | Evidence / scope |
| --- | --- | --- |
| Existing attacks | Ready | Original 4 dev and 6 held-out files unchanged; chat/description injection, spoofing, booking, budget and canary endpoints mapped in protocol. Historical exposure limits an unseen-payload claim. |
| Matched off/on boundary replay | Ready | One candidate, identical trusted context, two actual `check_action` decisions; no executable tool/config dispatcher invented. Endpoints are explicitly counterfactual authorisation. |
| Model vs scripted separation | Ready | Distinct source fields and summaries; separate commands/directories. Strong prompt primary; weak prompt only a labelled optional stress ablation. |
| Safe controls and false positives | Ready | Five legitimate fixtures, five unsafe diagnostics; independent per-action labels, not benign-prompt intent or guard decisions. Legitimate description echo can count as a false block. |
| Error attribution | Ready | Target success, target-relevant blocking, no violation before guard, malformed output, API error and interruption remain distinct. |
| Collection/reproducibility | Ready | Cache forced off; fresh directory required; code/input/prompt/config snapshots and hashes, seeds/schedule, per-job results, retries/usage/timing and state. API errors preserve completed jobs and continue. |
| Canary privacy | Ready within stated local boundary | Private hierarchy 0700; raw files 0600; exact and case/separator-obfuscated markers redacted from report artifacts after classification. No encryption or protection from the same OS user/admin/backups. |
| Application boundaries | Unit-tested, limited scope | Existing bot tests exercise human confirmation, feasibility/current-profile/budget rechecks, and refusal to construct live Telegram with guards off. The synthetic tool-assistant experiment is not an end-to-end Telegram exploit test. |
| Validation | Passed | 269 tests, one existing Google SDK deprecation warning. Dev/held-out no-API schedules: 15/21 model jobs, all pending. Fake clients only in integration tests. |
| Security freeze / paid execution | Pending | Review, commit the security package, then explicit approval. Do not modify frozen planning artifacts or tune against held-out security outcomes. |

Implementation files: `tripbot/eval/security.py`, `security_policy.py`; safer CLI forwarding in `tripbot/eval/attacks.py`; `data/security_controls_v1.json`; `tests/test_security_eval.py` and updated legacy CLI test; security section of `README.md`. Protocol: `SECURITY_EVALUATION_PROTOCOL.md`.

Report-facing outputs: `manifest.json`, `schedule.json`, `state.json`, `inputs/`, `source/`, `jobs/<id>/result.json`, redacted `calls.jsonl`, `runs.jsonl`, `summary.json`, `summary.csv`, `pairs.csv`. Private evidence remains under `private/`, never for report sharing. Offline summary rebuild never reads raw secrets or builds an API client.

Main limitations: only 4/6 existing payloads; repeated runs are not new attacks; counterfactual boundary outcomes differ from actual exploitability; live Telegram has no guard-off or arbitrary model tool dispatcher; raw-chat/profile extraction and adaptive multi-turn attacks are not covered; no real external booking/exfiltration; finite canary-normalisation checks; restricted independent safety labels; provider-controlled model alias. No guard/product fixes are made to improve measured defences.
