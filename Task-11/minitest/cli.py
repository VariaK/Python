import argparse
import sys
import os
from collections import defaultdict

from .discovery import discover_tests
from .fixtures import FIXTURE_REGISTRY
from .execution import TestRunner

def format_time(seconds):
    return f"{seconds:.2f}s"

def main():
    parser = argparse.ArgumentParser(description="minitest - miniature testing framework")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("path", help="Path to tests directory")
    parser.add_argument("--parallel", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.command == "run":
        run_tests(args)

def run_tests(args):
    start_dir = os.path.abspath(args.path)
    if not os.path.isdir(start_dir):
        print(f"Error: {args.path} is not a directory")
        sys.exit(1)
        
    # We must ensure the current directory is in sys.path
    # so that imports in test files resolve correctly.
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
        
    tasks, conftest_files = discover_tests(start_dir)
    
    modules = set(t['module_path'] for t in tasks)
    
    print("\n=== Test Discovery ===")
    print(f"Found {len(tasks)} tests across {len(modules)} modules")
    
    if FIXTURE_REGISTRY:
        fixtures_list = [f"{name} ({info['scope']})" for name, info in FIXTURE_REGISTRY.items()]
        print(f"Fixtures loaded: {', '.join(fixtures_list)}")
        
    print(f"\n=== Execution ({args.parallel} worker{'s' if args.parallel > 1 else ''}) ===")
    
    runner = TestRunner(parallel=args.parallel)
    
    import time
    start_time = time.time()
    
    results = runner.run(tasks, conftest_files)
    
    total_time = time.time() - start_time
    
    # Group results by module for printing
    results_by_module = defaultdict(list)
    for res in results:
        results_by_module[res['module_path']].append(res)
        
    passed = 0
    failed = 0
    skipped = 0
    slowest_test = None
    max_time = -1
    
    for module_path, mod_results in results_by_module.items():
        # Make path relative for cleaner output
        try:
            rel_path = os.path.relpath(module_path, os.getcwd())
        except ValueError:
            rel_path = module_path
            
        # Format paths with forward slashes for consistent display
        rel_path = rel_path.replace("\\", "/")
        print(f"\n{rel_path}")
        
        for res in mod_results:
            status = res['status']
            name = res['test_name']
            t = res['time']
            reason = res['reason']
            
            if status == 'PASS':
                passed += 1
                print(f"  PASS  {name:<50} [{format_time(t)}]")
            elif status == 'SKIP':
                skipped += 1
                reason_str = f" (skipped: {reason})" if reason else " (skipped)"
                print(f"  SKIP  {name}{reason_str:<{50 - len(name)}} [{format_time(t)}]")
            elif status == 'FAIL':
                failed += 1
                print(f"  FAIL  {name:<50} [{format_time(t)}]")
                if res['error_msg']:
                    # Indent error message
                    for line in res['error_msg'].split('\n'):
                        print(f"        {line}")
                        
            if t > max_time:
                max_time = t
                slowest_test = name
                
    print("\n=== Summary ===")
    print(f"{len(tasks)} tests | {passed} passed | {failed} failed | {skipped} skipped")
    print(f"Total time: {format_time(total_time)} (parallel across {args.parallel} workers)")
    if slowest_test:
        print(f"Slowest: {slowest_test} ({format_time(max_time)})")
        
    if failed > 0:
        sys.exit(1)
