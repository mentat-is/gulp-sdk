#!/usr/bin/env python3
"""
Generic Python package build and upload script.

Usage:
    python build_and_upload.py [--test]

Features:
    1. Builds the Python package (source distribution and wheel)
    2. Optionally uploads to PyPI using twine
    3. Reads PYPI_API_TOKEN from environment variable
    4. Supports --test flag for test.pypi.org
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def ensure_twine_installed() -> None:
    """Ensure twine is installed, install if not present."""
    try:
        subprocess.run([sys.executable, "-m", "twine", "--version"], 
                      check=True, capture_output=True)
        print("✓ twine is already installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("twine not found. Installing twine...")
        run_command([sys.executable, "-m", "pip", "install", "twine"])


def clean_dist() -> None:
    """Remove old distribution files."""
    dist_dir = Path("dist")
    if dist_dir.exists():
        # delete directory tree
        print("Cleaning old distribution files...")
        shutil.rmtree(dist_dir)
        print("✓ Cleaned dist/ directory")


def build_package() -> None:
    """Build the Python package (sdist and wheel)."""
    print("\n=== Building Package ===")

    # Ensure build tools are available
    try:
        subprocess.run([sys.executable, "-m", "build", "--version"], 
                      check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("build module not found. Installing build...")
        run_command([sys.executable, "-m", "pip", "install", "build"])

    # Clean old builds
    clean_dist()

    # Build the package
    run_command([sys.executable, "-m", "build"])
    print("✓ Package built successfully")

    # List built files
    dist_dir = Path("dist")
    if dist_dir.exists():
        print("\nBuilt files:")
        for file in dist_dir.iterdir():
            print(f"  - {file}")


def upload_package(use_test_pypi: bool = False) -> None:
    """Upload the package to PyPI using twine."""
    print("\n=== Uploading to PyPI ===")

    # Ensure twine is installed
    ensure_twine_installed()

    # Check for API token
    api_token = os.environ.get("PYPI_API_TOKEN")
    if not api_token:
        print("Error: PYPI_API_TOKEN environment variable not set")
        print("Please set it with: export PYPI_API_TOKEN='your-token-here'")
        sys.exit(1)

    # Determine repository URL
    if use_test_pypi:
        repository_url = "https://test.pypi.org/legacy/"
        print("Uploading to: test.pypi.org")
    else:
        repository_url = "https://upload.pypi.org/legacy/"
        print("Uploading to: pypi.org")

    # Upload using twine
    cmd = [
        sys.executable, "-m", "twine",
        "upload",
        "--verbose",
        "--repository-url", repository_url,
        "-u", "__token__",
        "-p", api_token,
        "dist/*"
    ]

    # Use shell=True for wildcard expansion on Unix systems
    if os.name != 'nt':  # Unix-like systems
        result = subprocess.run(
            " ".join(cmd),
            shell=True,
            check=False
        )
    else:  # Windows
        # On Windows, expand the wildcard manually
        dist_files = list(Path("dist").glob("*"))
        if not dist_files:
            print("Error: No distribution files found in dist/")
            sys.exit(1)
        cmd = [
            sys.executable, "-m", "twine",
            "upload",
            "--verbose",
            "--repository-url", repository_url,
            "-u", "__token__",
            "-p", api_token,
        ] + [str(f) for f in dist_files]
        result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        print("✓ Upload successful!")
        if use_test_pypi:
            print("  View at: https://test.pypi.org/project/your-package/")
        else:
            print("  View at: https://pypi.org/project/your-package/")
    else:
        print("✗ Upload failed")
        sys.exit(1)


def check_package_long_description() -> None:
    """Check README and package metadata if available."""
    readme_files = ["README.md", "README.rst", "README.txt", "README"]
    found_readme = any(Path(f).exists() for f in readme_files)

    if not found_readme:
        print("⚠ Warning: No README file found")

    pyproject_toml = Path("pyproject.toml")
    setup_py = Path("setup.py")
    setup_cfg = Path("setup.cfg")

    if not any(f.exists() for f in [pyproject_toml, setup_py, setup_cfg]):
        print("Error: No pyproject.toml, setup.py, or setup.cfg found")
        print("This doesn't appear to be a Python package directory")
        sys.exit(1)

    print("✓ Package configuration found")


def main():
    parser = argparse.ArgumentParser(
        description="Build and upload Python packages to PyPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                   # Build only
    %(prog)s --test            # Build and upload to test.pypi.org (implies --upload)
    %(prog)s --upload          # Build and upload to pypi.org

Environment Variables:
    PYPI_API_TOKEN    Required for uploading (your PyPI/Test PyPI API token)
        """
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Upload to test.pypi.org instead of pypi.org (after building, implies --upload)"
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload to PyPI after building"
    )

    args = parser.parse_args()

    # If --test is specified, it implies --upload
    if args.test:
        args.upload = True

    print("Python Package Builder")
    print("=" * 40)

    # Check we're in a package directory
    check_package_long_description()

    # Build the package
    build_package()

    # Upload if requested
    if args.upload:
        upload_package(use_test_pypi=args.test)
    else:
        print("\n✓ Build complete. Use --upload to publish to PyPI.")
        print("  Use --test to upload to test.pypi.org")


if __name__ == "__main__":
    main()
