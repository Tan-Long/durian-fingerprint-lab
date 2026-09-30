#!/usr/bin/env python3
"""Train -> predict -> evaluate a per-target training-median reference baseline.

Usage: python3 scripts/morphology_baseline.py input.json --output result.json
Output must be a NEW file. Exit 0: all requested targets evaluated; 1: input/IO
error; 2: some targets blocked (successful targets are still written).

Input schema (one row per caller-attested canonical physical fruit):
  {"schema_version": 1,
   "feature_definitions": {"weight_g": {"timing": "before_opening",
     "attested_by": "reviewer", "evidence": "measurement protocol reference"}},
   "targets": ["locule_count", "aril_count", "shell_thickness_mm"],
   "fruits": [{"fruit_id": "F1", "split": "train",
     "features": {"weight_g": 1200},
     "targets": {"locule_count": {"value": 4, "review_status": "approved",
       "reviewed_by": "reviewer", "evidence": "review reference"}}}, ...]}

Supply at least one train and one test fruit and every requested target label.
Missing/bad/unapproved labels block ONLY their target, without dropping rows.
Feature timing attestations cover every supplied row; names cannot prove timing.
IDs must already resolve aliases to physical fruits; this tool cannot verify
identity or truthfulness of attestations. It never imports/approves workbook
labels, constructs splits, rounds predictions, or sets acceptance thresholds.

Features are validated but UNUSED: this constant baseline measures a reference
floor, not learned feature/image signal. Metrics are per fruit in target units;
fractional count predictions are deliberately retained. No accuracy acceptance
follows from running the tool. Authority: durian-two-track-pilot active plan,
Approach 5/6. Numeric label constraints match audit_morphology.TARGETS without
importing its optional Excel dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import sys


AUTHORITY = "docs/plans/active/durian-two-track-pilot.md (Approach 5/6)"
TARGETS = {"locule_count": (True, False), "aril_count": (True, True),
           "shell_thickness_mm": (False, False)}


def fail(item, rule, action):
    raise ValueError(f"{item}: {rule}; {action}. Authority: {AUTHORITY}")


def text_present(value):
    return isinstance(value, str) and bool(value.strip())


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_input(data):
    """Global gates: explicit, disjoint physical-fruit splits and pre-opening inputs."""
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        fail("input", "schema_version must be integer 1", "supply the documented input schema")
    targets = data.get("targets")
    if (not isinstance(targets, list) or not targets or
            any(not isinstance(t, str) or t not in TARGETS for t in targets) or
            len(set(targets)) != len(targets)):
        fail("targets", f"request unique targets from {list(TARGETS)}", "name each target once")
    definitions = data.get("feature_definitions")
    if not isinstance(definitions, dict) or not definitions:
        fail("feature_definitions", "explicit feature declarations required", "supply timing attestations")
    for name, definition in definitions.items():
        if not text_present(name) or not isinstance(definition, dict):
            fail(f"feature {name!r}", "invalid feature declaration", "supply a named timing declaration")
        if definition.get("timing") != "before_opening":
            fail(f"feature {name}", "only before_opening inputs allowed", "remove post-opening/unknown inputs")
        if not all(text_present(definition.get(k)) for k in ("attested_by", "evidence")):
            fail(f"feature {name}", "timing attestation missing", "supply reviewer and evidence for all rows")
    rows = data.get("fruits")
    if not isinstance(rows, list) or not rows:
        fail("fruits", "per-fruit rows required", "supply explicit train and test fruits")
    seen, splits = set(), set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not text_present(row.get("fruit_id")):
            fail(f"fruits[{index}]", "canonical fruit_id required", "resolve identity before running")
        fruit_id = row["fruit_id"]
        if fruit_id != fruit_id.strip():
            fail(f"fruit {fruit_id!r}", "fruit_id has surrounding whitespace", "provide an exact canonical ID")
        if fruit_id in seen:
            fail(f"fruit {fruit_id}", "duplicate fruit or train/test overlap", "use one row per physical fruit")
        seen.add(fruit_id)
        if row.get("split") not in ("train", "test"):
            fail(f"fruit {fruit_id}", "explicit train/test assignment required", "supply an approved split; no auto-split")
        splits.add(row["split"])
        features = row.get("features")
        if not isinstance(features, dict) or features.keys() != definitions.keys():
            fail(f"fruit {fruit_id}", "features must match declarations exactly", "supply all and only declared features")
        for name, value in features.items():
            if not finite_number(value):
                fail(f"fruit {fruit_id} feature {name}", "finite numeric feature required (not bool/null)", "review the input value")
    if splits != {"train", "test"}:
        fail("splits", "nonempty train and test sets required", "supply explicit disjoint fruit assignments")
    return rows


def target_problems(rows, target):
    problems = []
    integer, allow_zero = TARGETS[target]
    for row in rows:
        labels = row.get("targets")
        label = labels.get(target) if isinstance(labels, dict) else None
        reasons = []
        if not isinstance(label, dict):
            reasons.append("missing label")
        else:
            if label.get("review_status") != "approved":
                reasons.append("label not approved (audit valid is not approval)")
            if not all(text_present(label.get(k)) for k in ("reviewed_by", "evidence")):
                reasons.append("missing review attribution/evidence")
            value = label.get("value")
            if not finite_number(value):
                reasons.append("missing/nonfinite/nonnumeric label (bool excluded)")
            elif value < 0 or (value == 0 and not allow_zero):
                reasons.append("nonnegative label required" if allow_zero else "positive label required")
            elif integer and int(value) != value:
                reasons.append("integer count required")
        if reasons:
            problems.append({"fruit_id": row["fruit_id"], "split": row["split"], "reasons": reasons,
                             "action": "Review this target and supply approved finite values for every row; do not drop rows.",
                             "authority": AUTHORITY})
    return problems


def train(rows, target):
    """Fit a constant on validated TRAIN rows only; no features are used."""
    values = [row["targets"][target]["value"] for row in rows if row["split"] == "train"]
    # Half-sum avoids overflowing the addition in an even-sized median.
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    constant = median(ordered) if len(ordered) % 2 else ordered[midpoint - 1] / 2 + ordered[midpoint] / 2
    return {"kind": "training_median", "constant": constant, "train_count": len(values), "features_used": []}


def predict(model, rows):
    """Predict held-out rows without consulting target labels."""
    return [{"fruit_id": row["fruit_id"], "prediction": model["constant"]}
            for row in rows if row["split"] == "test"]


def evaluate(predictions, rows, target):
    truth = {row["fruit_id"]: row["targets"][target]["value"] for row in rows if row["split"] == "test"}
    errors = [item["prediction"] - truth[item["fruit_id"]] for item in predictions]
    count = len(errors)
    # Scaling keeps sum of squares finite for large (but finite) values.
    scale = max(abs(error) for error in errors)
    metrics = {"n": count, "mae": math.fsum(abs(error) / count for error in errors),
               "rmse": scale * math.sqrt(math.fsum((error / scale) ** 2 / count for error in errors)) if scale else 0.0,
               "bias": math.fsum(error / count for error in errors)}
    if not all(finite_number(value) for value in metrics.values()):
        raise ValueError("metric arithmetic exceeded finite numeric range")
    return metrics


def run(data):
    rows = validate_input(data)
    results = {}
    for target in data["targets"]:
        problems = target_problems(rows, target)
        if problems:
            results[target] = {"status": "blocked", "problems": problems}
            continue
        try:
            model = train(rows, target)
            predictions = predict(model, rows)
            metrics = evaluate(predictions, rows, target)
            results[target] = {"status": "evaluated", "model": model,
                               "predictions": predictions, "metrics": metrics}
        except (ValueError, OverflowError) as error:
            results[target] = {"status": "blocked", "problems": [{"reasons": [str(error)],
                               "action": "Check numeric scale; no rows were dropped."}]}
    return {"schema_version": 1, "status": "partial_block" if any(r["status"] == "blocked" for r in results.values()) else "evaluated",
            "user_acceptance": "pending", "features_used": [],
            "limits": "Features validated but UNUSED. Training-median reference floor, not learned feature signal. Caller attests canonical physical-fruit IDs, timing and label review; no automatic verification or product accuracy acceptance.",
            "feature_definitions": data["feature_definitions"],
            "splits": {split: [r["fruit_id"] for r in rows if r["split"] == split] for split in ("train", "test")},
            "targets": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New JSON result file; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        raw = args.input.read_bytes()
        result = run(json.loads(raw))
        result["source"] = {"path": str(args.input.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}
        serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        # Exclusive creation also rejects an existing source path or symlink.
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    except (ValueError, OSError) as error:
        print(f"morphology baseline: {error}", file=sys.stderr)
        return 1
    print(f"{result['status']}: " + ", ".join(f"{name}={value['status']}" for name, value in result["targets"].items()))
    return 2 if result["status"] == "partial_block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
