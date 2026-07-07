#!/usr/bin/env python3
"""
FreshMint: Automated Development Machine Provisioner
Reads a YAML configuration and provisions a new macOS or Linux machine
with system packages, Python tools, and VS Code extensions.
"""

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# --- Emoji Constants for Logging ---
ICON_RUN = "⏳"
ICON_OK = "✅"
ICON_FAIL = "❌"
ICON_WARN = "🚨"
ICON_OS = "🖥️"
ICON_PKG = "📦"
ICON_PY = "🐍"
ICON_VSC = "💻"
ICON_DRY = "🧪"


def log_info(message: str, icon: str = ICON_RUN) -> None:
    """Print an informational message to stdout."""
    print(f"{icon}  {message}")


def log_success(message: str) -> None:
    """Print a success message to stdout."""
    print(f"{ICON_OK}  {message}")


def log_error(message: str) -> None:
    """Print an error message to stderr."""
    print(f"{ICON_FAIL}  {message}", file=sys.stderr)


def log_warning(message: str) -> None:
    """Print a warning message to stderr."""
    print(f"{ICON_WARN}  {message}", file=sys.stderr)


def run_command(command: list[str], dry_run: bool = False) -> bool:
    """
    Safely execute a shell command using subprocess.
    
    Args:
        command: A list of strings representing the command and its arguments.
        dry_run: If True, print the command without executing it.
        
    Returns:
        True if the command succeeded (or was dry-run), False otherwise.
    """
    # Use shlex.join for accurate shell quoting in dry-run output
    cmd_str = shlex.join(command)
    
    if dry_run:
        log_info(f"[DRY RUN] {cmd_str}", icon=ICON_DRY)
        return True

    try:
        # Capture output to keep the terminal clean, rely on our logging
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        # Log the specific error returned by the system
        error_msg = e.stderr.strip() if e.stderr else "Unknown error"
        log_error(f"Command failed: {cmd_str}\n   -> {error_msg}")
        return False
    except FileNotFoundError:
        log_error(f"Command not found: {command[0]}")
        return False


def load_config(config_path: str) -> dict:
    """Parse the YAML configuration file."""
    path = Path(config_path)
    if not path.exists():
        log_error(f"Configuration file not found at {path}")
        sys.exit(1)
        
    with open(path, 'r', encoding='utf-8') as f:
        # FIX 7 (Re-fixed): Catch YAML syntax errors cleanly without raw tracebacks
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            log_error(f"Failed to parse YAML: {e}")
            sys.exit(1)
        
    # Catch empty files or files that don't resolve to a top-level dictionary
    if not config or not isinstance(config, dict):
        log_error(f"Configuration file is empty or invalid: {path}")
        sys.exit(1)
        
    return config


def detect_os() -> str:
    """Detect the host operating system. Returns 'macos' or 'linux'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    else:
        log_error(f"Unsupported operating system: {system}")
        sys.exit(1)


def check_command_exists(command: str) -> bool:
    """Check if a CLI command exists on the system PATH."""
    # Use shutil.which instead of spawning a subprocess
    return shutil.which(command) is not None


def ensure_homebrew(dry_run: bool) -> bool:
    """
    Check if Homebrew is installed. If not, attempt to install it.
    Returns True if Homebrew is available (or in dry-run).
    """
    if check_command_exists("brew"):
        return True

    log_warning("Homebrew is not installed.")
    
    # Return True on dry-run so the user can preview the package list
    if dry_run:
        log_info("[DRY RUN] Homebrew missing. Would attempt to install Homebrew first...", icon=ICON_DRY)
        return True

    # Prompt the user before running a remote install script
    try:
        response = input("🤔  Do you want to install Homebrew now? (y/n): ").strip().lower()
        if response == 'y':
            log_info("Installing Homebrew... (This may require sudo/password)")
            
            # SECURITY NOTE (6b): This intentionally uses the official curl-pipe-to-bash 
            # pattern mandated by Homebrew. It executes a remote script, which is inherently
            # risky, but is the standard, supported installation method on macOS.
            brew_install_cmd = [
                "/bin/bash", "-c",
                "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            ]
            
            # We don't use run_command here because we WANT to show the brew output 
            # as it gives the user interactive prompts and progress bars.
            result = subprocess.run(brew_install_cmd)
            
            if result.returncode == 0:
                log_success("Homebrew installed successfully!")
                # Add leading colon separator for PATH
                os.environ["PATH"] += ":/opt/homebrew/bin"
                return True
            else:
                log_error("Homebrew installation failed.")
                return False
        else:
            # Explicit feedback when user declines
            log_warning("Homebrew installation declined by user.")
    except KeyboardInterrupt:
        log_warning("Homebrew installation cancelled by user.")
    
    return False


def install_system_packages(config: dict, os_type: str, dry_run: bool) -> None:
    """Install system packages using Homebrew (macOS) or Apt (Linux)."""
    log_info(f"Preparing to install system packages for {os_type}...", icon=ICON_PKG)
    
    try:
        packages = config['system_packages'][os_type]
    except KeyError:
        log_warning(f"No system packages defined for '{os_type}' in config.yaml")
        return

    if not packages:
        log_warning("System packages list is empty.")
        return

    if os_type == "macos":
        if not ensure_homebrew(dry_run):
            log_error("Cannot install macOS packages without Homebrew.")
            return
            
        # Install individually to honor per-package failure tolerance
        for pkg in packages:
            cmd = ["brew", "install", pkg]
            if run_command(cmd, dry_run):
                log_success(f"Installed: {pkg}")
                
    elif os_type == "linux":
        if not check_command_exists("apt"):
            log_error("Apt package manager not found. Are you on a Debian/Ubuntu system?")
            return
            
        # Update apt lists first
        run_command(["sudo", "apt", "update", "-y"], dry_run)
        
        # Batched for performance. If it fails, it fails as a batch.
        cmd = ["sudo", "apt", "install", "-y"] + packages
        if run_command(cmd, dry_run):
            log_success(f"Installed {len(packages)} Linux packages via Apt")


def install_python_packages(config: dict, dry_run: bool) -> None:
    """Install global Python packages via pip3."""
    log_info("Preparing to install global Python packages...", icon=ICON_PY)
    
    packages = config.get('python_packages', [])
    if not packages:
        log_warning("No Python packages defined in config.yaml")
        return

    pip_cmd = "pip3"
    if not check_command_exists(pip_cmd):
        log_error(f"'{pip_cmd}' not found. Please install Python 3 first.")
        return

    # Attempt to upgrade pip. We intentionally ignore the return value here:
    # a failure to upgrade pip is non-fatal, and usually happens inside restricted
    # managed environments. As long as the subsequent package install succeeds, we're good.
    run_command([pip_cmd, "install", "--upgrade", "pip"], dry_run)

    # Batched for dependency resolution performance.
    cmd = [pip_cmd, "install", "--user"] + packages
    if run_command(cmd, dry_run):
        log_success(f"Installed {len(packages)} Python packages via {pip_cmd}")


def install_vscode_extensions(config: dict, dry_run: bool) -> None:
    """Install VS Code extensions via the `code` CLI."""
    log_info("Preparing to install VS Code extensions...", icon=ICON_VSC)
    
    extensions = config.get('vscode_extensions', [])
    if not extensions:
        log_warning("No VS Code extensions defined in config.yaml")
        return

    if not check_command_exists("code"):
        log_warning(
            "VS Code CLI ('code') not found in PATH. Skipping extensions.\n"
            "Tip: Open VS Code, press Cmd+Shift+P, and type 'Shell Command: Install code command in PATH'"
        )
        return

    # Install individually to honor per-package failure tolerance
    for ext in extensions:
        cmd = ["code", "--install-extension", ext]
        if run_command(cmd, dry_run):
            log_success(f"Installed VS Code Extension: {ext}")


def main() -> None:
    """Main execution entry point for FreshMint."""
    parser = argparse.ArgumentParser(
        description="FreshMint - Automate your development machine setup.",
        epilog="Example: python freshmint.py --dry-run"
    )
    parser.add_argument(
        "--config", 
        type=str, 
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Print all commands without executing them."
    )
    
    args = parser.parse_args()
    
    # Print Header
    print("\n" + "="*50)
    print("  🌿 FreshMint - Machine Provisioner")
    print("="*50 + "\n")
    
    if args.dry_run:
        log_info("DRY RUN MODE ACTIVE. No changes will be made.", icon=ICON_DRY)
        print("-" * 50)

    # 1. Load Configuration
    config = load_config(args.config)
    
    # 2. Detect OS
    os_type = detect_os()
    log_info(f"Detected Operating System: {os_type.upper()}", icon=ICON_OS)
    print("-" * 50)
    
    # 3. Execute Installation Pipelines
    install_system_packages(config, os_type, args.dry_run)
    print("-" * 50)
    
    install_python_packages(config, args.dry_run)
    print("-" * 50)
    
    install_vscode_extensions(config, args.dry_run)
    print("-" * 50)
    
    # 4. Finish
    log_success("FreshMint provisioning complete!")
    print()


if __name__ == "__main__":
    main()