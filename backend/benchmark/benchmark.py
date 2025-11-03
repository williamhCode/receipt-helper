#!/usr/bin/env python3
"""
Benchmark script to test API performance.
Compares sync vs async database implementations.

Usage:
    python benchmark.py [--concurrent N] [--iterations N] [--output results.json]
"""

import argparse
import asyncio
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Dict, Any

import requests

BASE_URL = "http://localhost:8000"


class BenchmarkRunner:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": []
        }

    def cleanup_test_data(self):
        """Clean up test groups created during benchmarking"""
        try:
            response = requests.get(f"{self.base_url}/groups/")
            if response.status_code == 200:
                groups = response.json()
                for group in groups:
                    if group["name"].startswith("Benchmark"):
                        requests.delete(f"{self.base_url}/groups/{group['id']}")
        except Exception as e:
            print(f"Cleanup warning: {e}")

    def benchmark_operation(self, name: str, func, iterations: int = 100):
        """Benchmark a single operation"""
        print(f"\n{'='*60}")
        print(f"Benchmarking: {name}")
        print(f"Iterations: {iterations}")
        print(f"{'='*60}")

        times = []
        errors = 0

        for i in range(iterations):
            start = time.perf_counter()
            try:
                func()
                elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
                times.append(elapsed)

                if (i + 1) % 10 == 0:
                    print(f"Progress: {i + 1}/{iterations}", end='\r')
            except Exception as e:
                errors += 1
                print(f"\nError on iteration {i + 1}: {e}")

        if times:
            result = {
                "name": name,
                "iterations": iterations,
                "errors": errors,
                "min_ms": min(times),
                "max_ms": max(times),
                "mean_ms": statistics.mean(times),
                "median_ms": statistics.median(times),
                "p95_ms": self._percentile(times, 0.95),
                "p99_ms": self._percentile(times, 0.99),
            }

            self.results["tests"].append(result)
            self._print_results(result)
            return result
        else:
            print("All iterations failed!")
            return None

    def benchmark_concurrent(self, name: str, func, iterations: int = 100, concurrent: int = 10):
        """Benchmark concurrent operations"""
        print(f"\n{'='*60}")
        print(f"Benchmarking (Concurrent): {name}")
        print(f"Total requests: {iterations}")
        print(f"Concurrent requests: {concurrent}")
        print(f"{'='*60}")

        times = []
        errors = 0

        def run_one():
            start = time.perf_counter()
            try:
                func()
                return (time.perf_counter() - start) * 1000
            except Exception as e:
                return None

        # Run concurrent requests
        start_total = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(run_one) for _ in range(iterations)]
            for i, future in enumerate(futures):
                result = future.result()
                if result is not None:
                    times.append(result)
                else:
                    errors += 1

                if (i + 1) % 10 == 0:
                    print(f"Progress: {i + 1}/{iterations}", end='\r')

        total_time = (time.perf_counter() - start_total) * 1000

        if times:
            result = {
                "name": f"{name} (concurrent={concurrent})",
                "iterations": iterations,
                "concurrent": concurrent,
                "errors": errors,
                "total_time_ms": total_time,
                "requests_per_second": iterations / (total_time / 1000),
                "min_ms": min(times),
                "max_ms": max(times),
                "mean_ms": statistics.mean(times),
                "median_ms": statistics.median(times),
                "p95_ms": self._percentile(times, 0.95),
                "p99_ms": self._percentile(times, 0.99),
            }

            self.results["tests"].append(result)
            self._print_results(result)
            return result
        else:
            print("All iterations failed!")
            return None

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of a list"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _print_results(self, result: Dict[str, Any]):
        """Pretty print benchmark results"""
        print(f"\n{result['name']}")
        print("-" * 60)
        if "requests_per_second" in result:
            print(f"Requests/sec:  {result['requests_per_second']:.2f}")
            print(f"Total time:    {result['total_time_ms']:.2f} ms")
        print(f"Mean:          {result['mean_ms']:.2f} ms")
        print(f"Median:        {result['median_ms']:.2f} ms")
        print(f"Min:           {result['min_ms']:.2f} ms")
        print(f"Max:           {result['max_ms']:.2f} ms")
        print(f"P95:           {result['p95_ms']:.2f} ms")
        print(f"P99:           {result['p99_ms']:.2f} ms")
        if result['errors'] > 0:
            print(f"Errors:        {result['errors']}")

    def save_results(self, filename: str):
        """Save results to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark Receipt Helper API")
    parser.add_argument("--concurrent", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--iterations", type=int, default=100, help="Number of iterations per test")
    parser.add_argument("--output", type=str, default="benchmark_results.json", help="Output file for results")
    args = parser.parse_args()

    runner = BenchmarkRunner()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           Receipt Helper API Benchmark Suite            ║
╚══════════════════════════════════════════════════════════╝

Configuration:
  - Base URL: {BASE_URL}
  - Iterations: {args.iterations}
  - Concurrent: {args.concurrent}
  - Output: {args.output}
""")

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✓ Server is running: {response.json()}")
    except Exception as e:
        print(f"✗ Error: Server not running at {BASE_URL}")
        print(f"  Start the server with: cd backend && python main.py")
        return

    # Clean up any previous test data
    print("\nCleaning up previous test data...")
    runner.cleanup_test_data()

    # Test 1: Simple GET request (root endpoint)
    runner.benchmark_operation(
        "GET / (health check)",
        lambda: requests.get(f"{BASE_URL}/"),
        iterations=args.iterations
    )

    # Test 2: List all groups
    runner.benchmark_operation(
        "GET /groups/ (list groups)",
        lambda: requests.get(f"{BASE_URL}/groups/"),
        iterations=args.iterations
    )

    # Test 3: Create group (with people)
    group_counter = {"count": 0}
    def create_group():
        group_counter["count"] += 1
        return requests.post(
            f"{BASE_URL}/groups/",
            json={
                "name": f"Benchmark Group {group_counter['count']}",
                "people": ["Alice", "Bob", "Charlie"]
            }
        )

    runner.benchmark_operation(
        "POST /groups/ (create group with 3 people)",
        create_group,
        iterations=50  # Fewer iterations since it creates data
    )

    # Test 4: Get specific group (with lazy loading)
    # First create a group to fetch
    test_group = requests.post(
        f"{BASE_URL}/groups/",
        json={
            "name": "Benchmark Fetch Test",
            "people": ["Alice", "Bob", "Charlie", "Dave"]
        }
    ).json()
    group_id = test_group["id"]

    runner.benchmark_operation(
        f"GET /groups/{group_id} (fetch group with relationships)",
        lambda: requests.get(f"{BASE_URL}/groups/{group_id}"),
        iterations=args.iterations
    )

    # Test 5: Create receipt with entries
    receipt_counter = {"count": 0}
    def create_receipt():
        receipt_counter["count"] += 1
        return requests.post(
            f"{BASE_URL}/groups/{group_id}/receipts/",
            json={
                "name": f"Benchmark Receipt {receipt_counter['count']}",
                "paid_by": "Alice",
                "people": ["Alice", "Bob", "Charlie"],
                "processed": False,
                "entries": [
                    {"name": "Item 1", "price": 10.50, "taxable": True, "assigned_to": ["Alice", "Bob"]},
                    {"name": "Item 2", "price": 15.75, "taxable": True, "assigned_to": ["Charlie"]},
                    {"name": "Item 3", "price": 8.25, "taxable": False, "assigned_to": ["Alice", "Bob", "Charlie"]},
                ]
            }
        )

    runner.benchmark_operation(
        "POST /receipts/ (create receipt with 3 entries)",
        create_receipt,
        iterations=30
    )

    # Test 6: Concurrent read operations
    runner.benchmark_concurrent(
        "GET /groups/ (concurrent)",
        lambda: requests.get(f"{BASE_URL}/groups/"),
        iterations=args.iterations,
        concurrent=args.concurrent
    )

    # Test 7: Concurrent group fetches
    runner.benchmark_concurrent(
        f"GET /groups/{group_id} (concurrent)",
        lambda: requests.get(f"{BASE_URL}/groups/{group_id}"),
        iterations=args.iterations,
        concurrent=args.concurrent
    )

    # Test 8: Concurrent mixed read/write
    mixed_counter = {"count": 0}
    def mixed_operation():
        mixed_counter["count"] += 1
        if mixed_counter["count"] % 3 == 0:
            # Write operation
            return requests.post(
                f"{BASE_URL}/groups/",
                json={"name": f"Benchmark Mixed {mixed_counter['count']}", "people": ["Alice"]}
            )
        else:
            # Read operation
            return requests.get(f"{BASE_URL}/groups/")

    runner.benchmark_concurrent(
        "Mixed read/write operations (concurrent)",
        mixed_operation,
        iterations=60,
        concurrent=args.concurrent
    )

    # Clean up test data
    print("\n\nCleaning up test data...")
    runner.cleanup_test_data()

    # Save results
    runner.save_results(args.output)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║                  Benchmark Complete!                     ║
╚══════════════════════════════════════════════════════════╝

Results saved to: {args.output}

To compare with another version:
1. Run benchmark on this branch: python benchmark.py --output sync_results.json
2. Switch branch: git checkout main
3. Run benchmark on main: python benchmark.py --output async_results.json
4. Compare results side by side
""")


if __name__ == "__main__":
    main()
