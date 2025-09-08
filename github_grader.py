#!/usr/bin/env python3
"""
GitHub Classroom Grader - Outputs bundle completion status for partial credit
This script runs the tests and exits with specific codes for GitHub Classroom
"""

import subprocess
import sys
import json
from pathlib import Path

def check_bundles():
    """Run tests and determine which bundles are complete"""
    try:
        # Run the test script
        result = subprocess.run(
            [sys.executable, "run_tests.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        output = result.stdout
        
        # Check for bundle completion in the output
        bundle1_complete = "✓" in output and "Bundle 1" in output
        bundle2_complete = "✓" in output and "Bundle 2" in output  
        bundle3_complete = "✓" in output and "Bundle 3" in output
        
        # Also check for grade levels
        has_c = "Grade Level Achieved:" in output and ("C" in output or "B" in output or "A" in output)
        has_b = "Grade Level Achieved:" in output and ("B" in output or "A" in output)
        has_a = "Grade Level Achieved:" in output and "A" in output
        
        return {
            "bundle1": bundle1_complete or has_c,
            "bundle2": bundle2_complete or has_b,
            "bundle3": bundle3_complete or has_a,
            "output": output
        }
    except Exception as e:
        print(f"Error running tests: {e}")
        return {
            "bundle1": False,
            "bundle2": False,
            "bundle3": False,
            "output": str(e)
        }

def main(bundle_number):
    """Check if a specific bundle is complete"""
    results = check_bundles()
    
    # Print the full output for visibility
    print(results["output"])
    print("\n" + "="*80)
    
    # Check the requested bundle
    if bundle_number == 1:
        if results["bundle1"]:
            print("✅ Bundle 1 COMPLETE")
            sys.exit(0)
        else:
            print("❌ Bundle 1 INCOMPLETE")
            sys.exit(1)
    elif bundle_number == 2:
        if results["bundle2"]:
            print("✅ Bundle 2 COMPLETE")
            sys.exit(0)
        else:
            print("❌ Bundle 2 INCOMPLETE")
            sys.exit(1)
    elif bundle_number == 3:
        if results["bundle3"]:
            print("✅ Bundle 3 COMPLETE")
            sys.exit(0)
        else:
            print("❌ Bundle 3 INCOMPLETE")
            sys.exit(1)
    else:
        print(f"Invalid bundle number: {bundle_number}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python github_grader.py <bundle_number>")
        sys.exit(1)
    
    try:
        bundle = int(sys.argv[1])
        main(bundle)
    except ValueError:
        print("Bundle number must be an integer (1, 2, or 3)")
        sys.exit(1)