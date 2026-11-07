# Historical evaluation documents

These documents preserve development decisions and pre-run checks. They are not the active final procedure. Pending/unmeasured statements reflect their original development checkpoints.

| Document | Historical purpose |
| --- | --- |
| [EVALUATION_LOG.md](EVALUATION_LOG.md) | Development iterations, preliminary runs and method changes |
| [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) | Earlier planning methodology, before the final freeze |
| [SECURITY_EVALUATION_PROTOCOL.md](SECURITY_EVALUATION_PROTOCOL.md) | Original V1 security measurement design |
| [SECURITY_EVALUATION_READINESS.md](SECURITY_EVALUATION_READINESS.md) | V1 implementation and pre-run readiness checks |
| [SECURITY_EVALUATION_READINESS_V2.md](SECURITY_EVALUATION_READINESS_V2.md) | Revised V2 measurement preparation and readiness checks |

The final protocols remain at repository root:

- [Final planning protocol](../../FINAL_EVALUATION_PROTOCOL.md).
- [Final security V2 protocol](../../SECURITY_EVALUATION_PROTOCOL_V2.md).
- [Project setup and completed outcomes](../../README.md).

Original documents captured inside frozen `results/**/source/` and `inputs/` remain unchanged. The executable runners now locate the moved historical protocols for source/input capture; no planning logic, prompts, guardrails, metric definitions or saved results changed.
