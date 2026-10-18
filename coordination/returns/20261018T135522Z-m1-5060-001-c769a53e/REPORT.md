# M1-5060-001 completed (exploratory only)

Input/frozen design commit: e43a80b21ae9e9b5142cb2097b10df1435c2556c.
Run: 20261018T134643Z-m1-boundary-efd3eb5b.

24 newly authored benign fragments, 216 format/control records and72 official document records;336 actual CPU FP32 forwards. Same fixed Prompt Guard weights and official score/threshold. No-CLS tail raises22/24 scores, median+0.054039; no format-only classification flips. One constructed split-core document false positive is confounded by tail content and length; stable deployment FPR effect unproven.48 identical-input position reexecutions have zero logit/score differences.

Commands: prepare.py -> freeze commit -> run.py -> analyze.py -> audit_candidates.py -> verify.py -> finalize.py, all under ingress_detection_pilot/stage_m1/. Verification PASS,405 preexisting tracked hashes unchanged. Raw in stage_m1/raw/20261018T134643Z-m1-boundary-efd3eb5b/. Full report mechanism_report.md, design independent_data_design.md, environment/schema/figures and exact hashes included.

Task2 inspected only20+20 publicly available rows for token-length/source feasibility, no detector calls. Common long support and independent source counts remain unproven;800-source collection not started. Full raw candidate PII remains local E cache; only hashes/counts committed.

No training, threshold tuning, new defense, LCMD, multiscale, historical rerun or5090 R2 access. Further mechanism work is a recommendation only; no next phase launched.
