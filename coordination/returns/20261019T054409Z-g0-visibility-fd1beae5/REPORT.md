# G0 immutable visibility audit

Task: G0-5090-001

Input commit: `44f64a4be3575dfc942b6287e4b1461dc2f858b6`

Run ID: `20261019T054409Z-g0-visibility-fd1beae5`

Status: `G0_HISTORICAL_VISIBILITY_AUDIT_COMPLETE_REVIEW_REQUIRED`

No model weights loaded or new forward/generation. Current base/adapter hashes are checked only on the source host. Static audit alone cannot decide all100 historical Resume cases. Native probability/logits were not stored. A=attack lost before/in token input; B=fully serialized but detector returned0; C=decision/interface inconsistency; D=coexisting A/C; E=insufficient evidence. B does not distinguish semantic/domain mismatch from length dilution or effective attention. No algorithm Go is authorized. See g0_audit.json for counts/evidence and explicit missing checks.
