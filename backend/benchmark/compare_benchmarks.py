#!/usr/bin/env python3
"""
Compare two benchmark results files.

Usage:
    python compare_benchmarks.py sync_results.json async_results.json
"""

import json
import sys
from typing import Dict, Any


def load_results(filename: str) -> Dict[str, Any]:
    """Load benchmark results from JSON file"""
    with open(filename, 'r') as f:
        return json.load(f)


def compare_results(sync_file: str, async_file: str):
    """Compare sync vs async benchmark results"""
    sync_results = load_results(sync_file)
    async_results = load_results(async_file)

    print(f"""
╔══════════════════════════════════════════════════════════════════════════╗
║              Sync vs Async Database Performance Comparison               ║
╚══════════════════════════════════════════════════════════════════════════╝

Sync Results:  {sync_file}
  Timestamp: {sync_results['timestamp']}

Async Results: {async_file}
  Timestamp: {async_results['timestamp']}

""")

    # Match tests by name
    sync_tests = {test['name']: test for test in sync_results['tests']}
    async_tests = {test['name']: test for test in async_results['tests']}

    print("=" * 120)
    print(f"{'Test Name':<50} {'Sync (ms)':<15} {'Async (ms)':<15} {'Diff':<15} {'Winner':<10}")
    print("=" * 120)

    for test_name in sorted(sync_tests.keys()):
        if test_name in async_tests:
            sync_test = sync_tests[test_name]
            async_test = async_tests[test_name]

            sync_mean = sync_test['mean_ms']
            async_mean = async_test['mean_ms']
            diff_pct = ((sync_mean - async_mean) / async_mean) * 100

            winner = "SYNC" if sync_mean < async_mean else "ASYNC"
            if abs(diff_pct) < 5:
                winner = "TIE"

            diff_str = f"{diff_pct:+.1f}%"

            print(f"{test_name:<50} {sync_mean:>10.2f} ms  {async_mean:>10.2f} ms  {diff_str:>10}    {winner:<10}")

    print("=" * 120)
    print()

    # Detailed comparison for key metrics
    print("Detailed Metrics Comparison")
    print("=" * 120)

    for test_name in sorted(sync_tests.keys()):
        if test_name in async_tests:
            sync_test = sync_tests[test_name]
            async_test = async_tests[test_name]

            print(f"\n{test_name}")
            print("-" * 80)

            metrics = [
                ("Mean", "mean_ms"),
                ("Median", "median_ms"),
                ("P95", "p95_ms"),
                ("P99", "p99_ms"),
                ("Min", "min_ms"),
                ("Max", "max_ms"),
            ]

            for label, key in metrics:
                if key in sync_test and key in async_test:
                    sync_val = sync_test[key]
                    async_val = async_test[key]
                    diff_pct = ((sync_val - async_val) / async_val) * 100 if async_val > 0 else 0

                    print(f"  {label:<10} Sync: {sync_val:>8.2f} ms | Async: {async_val:>8.2f} ms | Diff: {diff_pct:>+6.1f}%")

            # Show throughput for concurrent tests
            if "requests_per_second" in sync_test and "requests_per_second" in async_test:
                sync_rps = sync_test["requests_per_second"]
                async_rps = async_test["requests_per_second"]
                diff_pct = ((sync_rps - async_rps) / async_rps) * 100 if async_rps > 0 else 0
                print(f"  {'RPS':<10} Sync: {sync_rps:>8.2f}     | Async: {async_rps:>8.2f}     | Diff: {diff_pct:>+6.1f}%")

    # Summary
    print(f"\n{'=' * 120}")
    print("SUMMARY")
    print("=" * 120)

    sync_wins = 0
    async_wins = 0
    ties = 0

    for test_name in sync_tests.keys():
        if test_name in async_tests:
            sync_mean = sync_tests[test_name]['mean_ms']
            async_mean = async_tests[test_name]['mean_ms']
            diff_pct = abs((sync_mean - async_mean) / async_mean) * 100

            if diff_pct < 5:
                ties += 1
            elif sync_mean < async_mean:
                sync_wins += 1
            else:
                async_wins += 1

    total = sync_wins + async_wins + ties
    print(f"\nOut of {total} comparable tests:")
    print(f"  Sync faster:  {sync_wins} tests ({sync_wins/total*100:.1f}%)")
    print(f"  Async faster: {async_wins} tests ({async_wins/total*100:.1f}%)")
    print(f"  Tie (<5%):    {ties} tests ({ties/total*100:.1f}%)")

    avg_diff = []
    for test_name in sync_tests.keys():
        if test_name in async_tests:
            sync_mean = sync_tests[test_name]['mean_ms']
            async_mean = async_tests[test_name]['mean_ms']
            diff_pct = ((sync_mean - async_mean) / async_mean) * 100
            avg_diff.append(diff_pct)

    if avg_diff:
        overall_avg = sum(avg_diff) / len(avg_diff)
        print(f"\nOverall average difference: {overall_avg:+.1f}%")
        if overall_avg > 5:
            print("  → Async is meaningfully faster on average")
        elif overall_avg < -5:
            print("  → Sync is meaningfully faster on average")
        else:
            print("  → Performance is essentially equivalent")

    print()


def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_benchmarks.py <sync_results.json> <async_results.json>")
        sys.exit(1)

    sync_file = sys.argv[1]
    async_file = sys.argv[2]

    try:
        compare_results(sync_file, async_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nMake sure you've run benchmarks on both branches:")
        print("  1. On sync branch: python benchmark.py --output sync_results.json")
        print("  2. On async branch: python benchmark.py --output async_results.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
