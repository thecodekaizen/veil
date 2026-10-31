"""Run the deterministic discovery engine against labeled synthetic seed cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .cli import DatasetError
from .service import discover_dataset

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "datasets" / "synthetic" / "evaluation-cases.json"


def evaluate(manifest_path: Path) -> tuple[list[dict[str, Any]], int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        dataset_path = (manifest_path.parent / case["dataset"]).resolve()
        try:
            finding = discover_dataset(dataset_path=dataset_path, provider_name="fixture")
            actual = {
                "earlier_theme": finding["earlier_theme"],
                "later_theme": finding["later_theme"],
            }
        except DatasetError as exc:
            actual = f"invalid:{exc.code}"
        except ValueError as exc:
            actual = None if str(exc).startswith("No sufficiently supported evolution finding") else "invalid:discovery"

        expected = case["expected"]
        passed = actual == expected
        results.append({"name": case["name"], "expected": expected, "actual": actual, "passed": passed})
    return results, sum(1 for item in results if item["passed"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate THREAD discovery on labeled synthetic seed cases.")
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    try:
        results, passed = evaluate(args.manifest)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} · {result['name']}: expected {result['expected']}, got {result['actual']}")
    print(f"\n{passed}/{len(results)} seed cases matched their expected outcome.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
