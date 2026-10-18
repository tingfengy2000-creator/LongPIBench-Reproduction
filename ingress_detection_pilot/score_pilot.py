#!/usr/bin/env python3
"""Offline feasibility evaluator for document-level prompt injection detection.

Research scaffold only: does not load an LLM, detector, or LongPIBench.
Input is newline-delimited JSON with real cached per-chunk detector scores.

Required row schema:
  {"sample_id":"resume-0-clean", "source_document_id":"resume-0",
   "split":"calibration" | "test", "domain":"resume" | "email",
   "label":0 | 1, "token_count":12345, "chunk_scores":[0.01, 0.09]}

Labels: 0=benign, 1=attack. Higher score means more suspicious.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            o = json.loads(line)
            for k in ("sample_id", "source_document_id", "split", "domain", "label", "token_count", "chunk_scores"):
                if k not in o:
                    raise ValueError(f"line {line_no}: missing {k}")
            if o["split"] not in {"calibration", "test"} or o["label"] not in (0, 1):
                raise ValueError(f"line {line_no}: invalid split/label")
            if not isinstance(o["chunk_scores"], list) or not o["chunk_scores"]:
                raise ValueError(f"line {line_no}: chunk_scores must be nonempty")
            scores = [float(x) for x in o["chunk_scores"]]
            if not all(math.isfinite(x) for x in scores):
                raise ValueError(f"line {line_no}: invalid score")
            if int(o["token_count"]) < 1:
                raise ValueError(f"line {line_no}: bad token_count")
            o["chunk_scores"] = scores
            o["n_chunks"] = len(scores)
            rows.append(o)
    if not rows:
        raise ValueError("empty input")
    if len({r["sample_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate sample_id")
    origin_splits = defaultdict(set)
    for r in rows:
        origin_splits[r["source_document_id"]].add(r["split"])
    leaks = [k for k, v in origin_splits.items() if len(v) > 1]
    if leaks:
        raise ValueError(f"source-document split leakage detected: {leaks[:5]}")
    return rows


def quantile90(sorted_scores):
    # linear interpolation for an explicitly descriptive 90th percentile baseline
    if len(sorted_scores) == 1:
        return sorted_scores[0]
    p = .9 * (len(sorted_scores) - 1)
    lo, hi = int(p), math.ceil(p)
    return sorted_scores[lo] + (p - lo) * (sorted_scores[hi] - sorted_scores[lo])


def basic_score(r, method):
    ss = sorted(r["chunk_scores"], reverse=True)
    if method == "max":
        return ss[0]
    if method == "top2":
        return sum(ss[:2]) / len(ss[:2])
    if method == "q90":
        return quantile90(sorted(ss))
    raise ValueError(method)


def conditional_pvalue(row, clean_calibration, exclude_self=False):
    # Nearest neighbors in log(1+chunks) approximate length conditioning.
    # 20 benign calibration documents minimum; fall back to entire clean set.
    others = [c for c in clean_calibration if not (exclude_self and c["sample_id"] == row["sample_id"])]
    if not others:
        raise ValueError("need at least 2 benign calibration documents for length calibration")
    target = math.log1p(row["n_chunks"])
    ordered = sorted(others, key=lambda r: (abs(math.log1p(r["n_chunks"]) - target), r["sample_id"]))
    k = min(len(ordered), max(20, math.ceil(.35 * len(ordered))))
    neighborhood = ordered[:k]
    value = basic_score(row, "max")
    count = sum(basic_score(c, "max") >= value for c in neighborhood)
    return (1 + count) / (1 + len(neighborhood))


def score(row, method, clean_calibration, for_calibration=False):
    if method != "length_calibrated_max":
        return basic_score(row, method)
    p = conditional_pvalue(row, clean_calibration, exclude_self=for_calibration)
    return -math.log10(p)


def threshold_at_empirical_fpr(clean_scores, alpha):
    # For high-score-is-attack, choose the most permissive threshold that
    # yields <= floor(alpha*n) FPs on clean calibration examples.
    vals = sorted(clean_scores, reverse=True)
    k = math.floor(alpha * len(vals))
    if k >= len(vals):
        return float("-inf")
    return math.nextafter(vals[k], float("inf"))


def confusion(rows, method, t, cal_clean):
    tp = fp = tn = fn = 0
    for row in rows:
        predicted = score(row, method, cal_clean) > t
        if row["label"]:
            if predicted: tp += 1
            else: fn += 1
        else:
            if predicted: fp += 1
            else: tn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "tpr": (tp / (tp + fn)) if tp + fn else None,
            "fpr": (fp / (fp + tn)) if fp + tn else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="pilot_results.json")
    ap.add_argument("--fpr-budget", type=float, default=.10)
    args = ap.parse_args()
    if not (0 < args.fpr_budget < 1):
        ap.error("--fpr-budget must lie within (0,1)")
    rows = read_jsonl(Path(args.input))
    calibration = [r for r in rows if r["split"] == "calibration"]
    test = [r for r in rows if r["split"] == "test"]
    clean_cal = [r for r in calibration if r["label"] == 0]
    if len(clean_cal) < 3 or not test:
        ap.error("need >=3 calibration clean rows and nonempty test split")

    methods = ("max", "top2", "q90", "length_calibrated_max")
    report = {"warning": "Exploratory score replay only; not actual performance unless real detector scores are supplied.",
              "fpr_budget": args.fpr_budget,
              "n_calibration_clean": len(clean_cal), "n_test": len(test), "methods": {}}
    for method in methods:
        calib_vals = [score(r, method, clean_cal, for_calibration=True) for r in clean_cal]
        t = threshold_at_empirical_fpr(calib_vals, args.fpr_budget)
        per_domain = {}
        for domain in sorted({r["domain"] for r in test}):
            domain_rows = [r for r in test if r["domain"] == domain]
            per_domain[domain] = confusion(domain_rows, method, t, clean_cal)
        report["methods"][method] = {"calibration_threshold": t,
                                     "test_overall": confusion(test, method, t, clean_cal),
                                     "test_by_domain": per_domain}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output}; exploratory results only; no real model has been called.")
    for k, v in report["methods"].items():
        print(k, v["test_overall"])

if __name__ == "__main__":
    main()
