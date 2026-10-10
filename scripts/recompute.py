"""Recompute the headline numbers of docs/evaluation.md and docs/validation.md from the CSV files in data/.

    python scripts/recompute.py

Standard library only. Prints the totals per provider and column, the paired comparisons with their sign-test
p values, and the summary of the end-to-end test.
"""

import csv
import statistics
from math import comb
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def rows(rel):
    with open(DATA / rel, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sign_test(a, b):
    """Two-sided exact sign test for a wins against b wins."""
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, k) for k in range(min(a, b) + 1)) / 2**n)


def pairs(score_a, score_b):
    """Queries only a got right, queries only b got right, over the queries both were scored on."""
    common = [q for q in score_a if q in score_b]
    return sum(score_a[q] > score_b[q] for q in common), sum(score_a[q] < score_b[q] for q in common)


def scores(results, column, field, runs=None):
    return {
        (r["run"], r["query_id"]): int(r[field])
        for r in results
        if r["column"] == column and r[field] != "" and (runs is None or r["run"] in runs)
    }


def median(values):
    values = [float(v) for v in values if v != ""]
    return round(statistics.median(values), 2) if values else None


def main():
    print("Run 1: correct from the result list and with result pages, of 55; current version in a snippet, of 10")
    run1 = rows("provider-comparison/run1-results.csv")
    for column in ("exa", "parallel", "firecrawl", "tinyfish", "brave", "tavily", "keenable"):
        mine = [r for r in run1 if r["column"] == column]
        listed = sum(int(r["correct_from_result_list"]) for r in mine if r["correct_from_result_list"] != "")
        with_pages = sum(int(r["correct_with_result_pages"]) for r in mine if r["correct_with_result_pages"] != "")
        current = sum(r["detail"].startswith("snippet: current version") for r in mine)
        seconds, chars = median(r["seconds"] for r in mine), median(r["chars"] for r in mine)
        print(f"  {column:10s} {listed:3d} {with_pages:3d}  current {current:2d}  {seconds} s  {chars} chars")

    print("\nRun 2: correct from the result list (main set of 55, extra block of 20, both)")
    run2 = rows("provider-comparison/run2-results.csv")
    columns = rows("provider-comparison/columns.csv")
    for c in columns:
        main_set = sum(scores(run2, c["column"], "correct_from_result_list", {"run2-main"}).values())
        extra = sum(scores(run2, c["column"], "correct_from_result_list", {"run2-extra"}).values())
        mine = [r for r in run2 if r["column"] == c["column"]]
        seconds, chars = median(r["seconds"] for r in mine), median(r["chars"] for r in mine if r["run"] == "run2-main")
        print(f"  {c['column']:28s} {main_set:3d} {extra:3d} {main_set + extra:3d}  {seconds} s  {chars} chars")

    print("\nRun 2: variants against their baseline (only variant : only baseline, p)")
    for c in columns:
        if c["variant_of"]:
            a, b = pairs(
                scores(run2, c["column"], "correct_from_result_list"),
                scores(run2, c["variant_of"], "correct_from_result_list"),
            )
            print(f"  {c['column']:28s} vs {c['variant_of']:9s} {a:2d} : {b:2d}  p {sign_test(a, b):.3f}")

    print("\nEnd-to-end test: per setup")
    e2e = rows("end-to-end/results.csv")
    category = {q["id"]: q["category"] for q in rows("end-to-end/questions.csv")}
    setups = ("exa-capped", "exa-uncapped", "parallel-v1", "parallel-beta-builtin")
    for setup in setups:
        mine = [r for r in e2e if r["setup"] == setup]
        by_category = {
            c: sum(r["verdict"] == "correct" for r in mine if category[r["id"]] == c)
            for c in ("fact", "error", "current")
        }
        tokens = {
            c: sum(int(r["input_tokens"]) for r in mine if category[r["id"]] == c) for c in ("fact", "error", "current")
        }
        searches, fetches = sum(int(r["searches"]) for r in mine), sum(int(r["page_fetches"]) for r in mine)
        print(
            f"  {setup:22s} correct {sum(by_category.values())} {by_category}  searches {searches}"
            f"  fetches {fetches}  input tokens {sum(tokens.values())} {tokens}"
        )
        print(
            f"  {'':22s} medians: result chars {median(r['search_result_chars_median'] for r in mine)}, input tokens "
            f"{median(r['input_tokens'] for r in mine)}, search {median(r['search_seconds_median'] for r in mine)} s, "
            f"total {median(r['total_seconds'] for r in mine)} s, model {median(r['model_seconds'] for r in mine)} s"
        )

    print("\nEnd-to-end test: pairs (only A correct : only B correct, p; median difference A - B)")
    cell = {(r["setup"], r["id"]): r for r in e2e}
    for a, b in (
        ("exa-capped", "exa-uncapped"),
        ("parallel-v1", "parallel-beta-builtin"),
        ("exa-capped", "parallel-beta-builtin"),
    ):
        right_a = {q: int(cell[(a, q)]["verdict"] == "correct") for q in category}
        right_b = {q: int(cell[(b, q)]["verdict"] == "correct") for q in category}
        only_a, only_b = pairs(right_a, right_b)
        print(f"  {a} vs {b}: {only_a} : {only_b}  p {sign_test(only_a, only_b):.3f}")
        for field in ("search_seconds_median", "input_tokens", "total_seconds", "page_fetches"):
            diffs = [
                float(cell[(a, q)][field]) - float(cell[(b, q)][field])
                for q in category
                if cell[(a, q)][field] != "" and cell[(b, q)][field] != ""
            ]
            lower_a, lower_b = sum(d < 0 for d in diffs), sum(d > 0 for d in diffs)
            middle = statistics.median(diffs)
            print(
                f"      {field:22s} median {middle:9.2f}   A lower in {lower_a}, B lower in {lower_b}, of {len(diffs)}"
            )


if __name__ == "__main__":
    main()
