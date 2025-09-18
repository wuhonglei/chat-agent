#!/usr/bin/env python3
"""
Code formatting script using ruff
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run command and handle output"""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.stdout:
            print(f"Output:\n{result.stdout}")

        if result.stderr:
            print(f"Error:\n{result.stderr}")

        if result.returncode != 0:
            print(f"Warning: {description} returned non-zero exit code {result.returncode}")
            return False
        else:
            print(f"✓ {description} completed")
            return True

    except FileNotFoundError:
        print(f"Error: Command {cmd[0]} not found")
        return False
    except Exception as e:
        print(f"Error: Exception occurred while running {description}: {e}")
        return False


def check_tools():
    """Check if required tools are installed"""
    tools = ["ruff"]
    missing_tools = []

    for tool in tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            print(f"✓ {tool} is installed")
        except (FileNotFoundError, subprocess.CalledProcessError):
            missing_tools.append(tool)
            print(f"✗ {tool} is not installed")

    if missing_tools:
        print("\nPlease install missing tools:")
        for tool in missing_tools:
            print(f"  pip install {tool}")
        return False

    return True


def format_code(target_path="."):
    """Format code using ruff"""
    target_path = Path(target_path).resolve()

    if not target_path.exists():
        print(f"Error: Path {target_path} does not exist")
        return False

    print(f"Formatting target: {target_path}")

    original_cwd = os.getcwd()
    os.chdir(target_path)

    try:
        success = True

        print("\n=== Ruff linting and fixing ===")
        if not run_command(["ruff", "check", "--fix", "."], "Ruff linting and fixing"):
            success = False

        print("\n=== Ruff formatting ===")
        if not run_command(["ruff", "format", "."], "Ruff formatting"):
            success = False

        return success

    finally:
        os.chdir(original_cwd)


def main():
    """Main function"""
    print("Python Code Formatting Script")
    print("=" * 40)

    if not check_tools():
        sys.exit(1)

    target = sys.argv[1] if len(sys.argv) > 1 else "."

    print("\nStarting code formatting...")

    if format_code(target):
        print("\n✓ Code formatting completed!")
    else:
        print("\n✗ Issues occurred during code formatting")
        sys.exit(1)


if __name__ == "__main__":
    main()
