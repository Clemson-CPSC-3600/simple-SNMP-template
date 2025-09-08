#!/usr/bin/env python3
"""
Test Runner with Specification Grading Support
Runs tests organized by bundles (1, 2, 3) and reports grade level achieved.

This script:
- Runs tests with the existing src/ implementation
- Groups test results by bundle markers and shows specification grading progress
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import json

# ANSI color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'


class BundleTestRunner:
    def __init__(self, verbose=False):
        self.root_dir = Path(__file__).parent.absolute()
        self.src_dir = self.root_dir / "src"
        self.verbose = verbose
    
    def run_tests_with_json(self):
        """Run pytest with JSON output to get detailed test information including markers"""
        cmd = [sys.executable, "-m", "pytest"]
        cmd.append(str(self.root_dir / "tests"))
        cmd.extend([
            "--json-report",
            "--json-report-file=test_results.json",
            "-v",
            "--tb=short",
            "--color=yes",
        ])
        
        print(f"\nRunning: {' '.join(cmd)}")
        print("=" * 80)
        
        # Run pytest
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Print the output
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        # Parse JSON results
        bundles_data = self.parse_json_results()
        
        return result.returncode, bundles_data
    
    def parse_json_results(self):
        """Parse pytest-json-report output to extract bundle information"""
        bundles_data = {1: [], 2: [], 3: []}
        json_path = self.root_dir / "test_results.json"
        
        if not json_path.exists():
            print("Warning: JSON report file not found")
            return bundles_data
            
        try:
            with open(json_path, 'r') as f:
                json_data = json.load(f)
            
            # Parse test results from JSON
            if 'tests' in json_data:
                for test in json_data['tests']:
                    nodeid = test.get('nodeid', '')
                    outcome = test.get('outcome', '')
                    
                    # Parse test components from nodeid
                    parts = nodeid.split('::')
                    filename = parts[0].split('/')[-1] if parts else 'unknown'
                    test_name = parts[-1] if len(parts) > 1 else 'unknown'
                    test_class = parts[1] if len(parts) > 2 else None
                    
                    # Get bundle and points from metadata (added by our hook)
                    metadata = test.get('metadata', {})
                    bundle = metadata.get('bundle', 1)
                    points = metadata.get('points', 0)
                    
                    bundles_data[bundle].append({
                        'file': filename,
                        'class': test_class,
                        'name': test_name,
                        'passed': outcome == 'passed',
                        'points': points
                    })
                    
                    if self.verbose:
                        status_icon = "✓" if outcome == 'passed' else "✗"
                        print(f"  {status_icon} Bundle {bundle}: {test_name} ({points} points)")
            
            # Clean up JSON file
            json_path.unlink()
            
        except Exception as e:
            print(f"Error parsing JSON results: {e}")
            import traceback
            if self.verbose:
                traceback.print_exc()
        
        return bundles_data
    
    def run_tests_standard(self):
        """Run pytest and collect bundle information"""
        # pytest-json-report is a required dependency
        try:
            import pytest_jsonreport
        except ImportError:
            print("\nERROR: pytest-json-report is not installed.")
            print("This is a required dependency for the test runner.")
            print("Please run: pip install -r requirements.txt")
            print("or: pip install pytest-json-report")
            sys.exit(1)
            
        return self.run_tests_with_json()
    
    def print_bundle_results(self, bundles_data):
        """Print test results organized by bundle"""
        # Calculate bundle completion
        bundle_status = {}
        for bundle in [1, 2, 3]:
            tests = bundles_data[bundle]
            total = len(tests)
            passed = sum(1 for t in tests if t['passed'])
            total_points = sum(t.get('points', 0) for t in tests)
            earned_points = sum(t.get('points', 0) for t in tests if t['passed'])
            
            bundle_status[bundle] = {
                'total': total,
                'passed': passed,
                'complete': total > 0 and passed == total,
                'total_points': total_points,
                'earned_points': earned_points
            }
        
        # Determine grade based on bundle completion
        grade = 'Not Passing'
        grade_color = RED
        points = 0
        
        if bundle_status[1]['complete']:
            grade = 'C'
            grade_color = BLUE
            points = 70
            if bundle_status[2]['complete']:
                grade = 'B'
                grade_color = YELLOW
                points = 85
                if bundle_status[3]['complete']:
                    grade = 'A'
                    grade_color = GREEN
                    points = 100
        
        # Print header
        print("\n" + "=" * 80)
        print(f"{BOLD}SPECIFICATION GRADING RESULTS{RESET}")
        print("=" * 80)
        print(f"\n{BOLD}Grade Level Achieved: {grade_color}{grade}{RESET}")
        print(f"{BOLD}Points Earned: {points}/100{RESET}\n")
        
        # Print bundle summaries
        bundle_names = {
            1: 'Bundle 1 (Core Requirements)',
            2: 'Bundle 2 (Intermediate Features)',
            3: 'Bundle 3 (Advanced Features)'
        }
        
        for bundle in [1, 2, 3]:
            status = bundle_status[bundle]
            if status['total'] == 0:
                print(f"⚪ {BOLD}{bundle_names[bundle]}{RESET}: No tests found")
                continue
                
            icon = f"{GREEN}✓{RESET}" if status['complete'] else f"{RED}✗{RESET}"
            completion = f"{status['passed']}/{status['total']}"
            percentage = (status['passed'] / status['total'] * 100) if status['total'] > 0 else 0
            
            points_str = ""
            if status['total_points'] > 0:
                points_str = f" ({status['earned_points']}/{status['total_points']} pts)"
            
            print(f"{icon} {BOLD}{bundle_names[bundle]}{RESET}: {completion} tests passed ({percentage:.0f}%){points_str}")
            
            if not status['complete'] and self.verbose:
                # Show failing tests
                failed_tests = [t for t in bundles_data[bundle] if not t['passed']]
                if failed_tests:
                    print(f"  {RED}Failed tests:{RESET}")
                    for test in failed_tests:
                        if test['class']:
                            print(f"    - {test['file']}::{test['class']}::{test['name']}")
                        else:
                            print(f"    - {test['file']}::{test['name']}")
        
        # Print requirements reminder
        print(f"\n{BOLD}Grading Requirements:{RESET}")
        print("• You must pass ALL tests in a bundle to receive credit")
        print("• Higher bundles require completion of all lower bundles")
        print("• Bundle 1 = 70 points (C), Bundle 1+2 = 85 points (B), All = 100 points (A)")
        
        # Next steps
        print(f"\n{BOLD}Next Steps:{RESET}")
        if not bundle_status[1]['complete']:
            print("→ Focus on Bundle 1 tests (core requirements)")
        elif not bundle_status[2]['complete']:
            print("→ Work on Bundle 2 tests (intermediate features)")
        elif not bundle_status[3]['complete']:
            print("→ Complete Bundle 3 tests (advanced features)")
        else:
            print(f"{GREEN}→ Congratulations! All bundles complete!{RESET}")
        
    def run(self):
        """Main execution method"""
        try:
            print("=" * 80)
            print(f"{BOLD}Test Runner with Specification Grading{RESET}")
            print("=" * 80)
            print(f"Root directory: {self.root_dir}")
            print(f"Testing implementation in: {self.src_dir}")
            
            # Check if src directory exists
            if not self.src_dir.exists():
                print(f"\n{RED}ERROR: src/ directory not found!{RESET}")
                print("Please ensure your implementation files are in the src/ directory.")
                return 1
            
            # Run tests directly
            exit_code, bundles_data = self.run_tests_standard()
            
            # Print bundle results
            self.print_bundle_results(bundles_data)
            
            return exit_code
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            return 2
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            if self.verbose:
                traceback.print_exc()
            return 3


def main():
    parser = argparse.ArgumentParser(
        description="Run tests with specification grading support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script runs tests organized by specification grading bundles:
- Bundle 1: Core requirements (70 points)
- Bundle 2: Intermediate features (85 points total)
- Bundle 3: Advanced features (100 points total)

Tests are assigned to bundles using pytest markers:
  @pytest.mark.bundle(1)  # Assigns test to Bundle 1
  @pytest.mark.points(10)  # Assigns point value to test

You must pass ALL tests in a bundle to receive credit for that level.

Examples:
  python run_tests.py           # Run all tests
  python run_tests.py -v        # Verbose output (shows failed tests)
"""
    )
    
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output (shows failed test details)")
    
    args = parser.parse_args()
    
    runner = BundleTestRunner(verbose=args.verbose)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())