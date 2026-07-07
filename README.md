# 🌿 FreshMint

**FreshMint** is a lightweight, Python-based system automation tool designed to instantly provision a brand-new development machine. By reading a simple `config.yaml` file, FreshMint handles the tedious parts of setting up a Mac or Linux machine so you can start coding immediately.

## ✨ Features

- **Cross-Platform Support:** Intelligently detects macOS (Homebrew) and Linux (Apt) and uses the correct package manager.
- **All-in-One Provisioning:** Installs system packages, global Python tools, and VS Code extensions in one command.
- **Robust Error Handling:** Uses Python's `subprocess` with strict error checking and safe output capturing to prevent silent failures. *(Note: Homebrew and VS Code extensions are installed individually so one failure won't block the rest. Apt and Pip are batched for performance and dependency resolution; if a batch fails, the script logs the error and continues to the next category).*
- **Dry Run Mode:** Test your configuration file before applying it using the `--dry-run` flag to see exactly what commands will run.
- **Graceful Dependency Handling:** If Homebrew is missing on macOS, FreshMint will warn you and offer to install it on the fly.
- **Beautiful Logging:** Clear, emoji-rich terminal output so you always know exactly what is happening.

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher installed.
- (For Linux) `sudo` privileges to run `apt`.

### Installation

1. **Fork or clone this repository:**
   ```bash
   git clone https://github.com/acookiefor2/FreshMint.git
   cd FreshMint
   ```

2. **Install the Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Customize your setup:**
   Edit the `config.yaml` file to include your favorite packages, Python tools, and VS Code extensions.

4. **Test your config (Recommended):**
   ```bash
   python3 freshmint.py --dry-run
   ```

5. **Provision your machine:**
   ```bash
   python3 freshmint.py
   ```

## ⚙️ Configuration

All provisioning is controlled via `config.yaml`. The file is divided into three main sections:

### 1. System Packages
Separated by OS to handle differing package names. 
```yaml
system_packages:
  macos:
    - git
    - zsh
  linux:
    - git
    - zsh
    - build-essential
```

### 2. Python Packages
Installed globally via `pip3 install --user`.
```yaml
python_packages:
  - black
  - flake8
  - poetry
```

### 3. VS Code Extensions
Installed via the VS Code CLI. *(Note: The `code` command must be installed in your PATH first. You can do this from inside VS Code via the Command Palette: `Shell Command: Install 'code' command in PATH`)*.
```yaml
vscode_extensions:
  - ms-python.python
  - esbenp.prettier-vscode
```

## 🧠 Design Decisions

A couple of behaviors that look like edge cases but are intentional:

- **Empty `config.yaml` hard-exits instead of running as a no-op.** A config with zero keys is almost always a mistake (e.g. the file got emptied out but never repopulated). Failing fast forces you to notice, rather than silently doing nothing and reporting success.
- **A failed `pip install --upgrade pip` doesn't stop the Python install.** In many corporate or managed environments, upgrading pip system-wide is blocked by permissions, but `pip install --user` still works fine. Treating the upgrade step as fatal would break the whole pipeline in exactly the environments where FreshMint is most useful.

## 🧪 Testing

FreshMint ships with a full `pytest` suite (`test_freshmint.py`) covering every function — command execution, config parsing, OS detection, Homebrew bootstrapping, and all three install pipelines. Nothing in the test suite touches your real system: `subprocess.run`, `shutil.which`, and `input()` are all mocked at the boundary, so no package manager is ever actually invoked.

### Running the tests

```bash
pip install pytest pytest-mock
pytest test_freshmint.py -v
```

35 tests, all passing, verified on both Linux and Windows.

## 🛠️ Advanced Usage

### Using a Custom Config File
If you have multiple machine profiles (e.g., `work.yaml`, `personal.yaml`), you can pass the file path via the `--config` flag:
```bash
python3 freshmint.py --config work.yaml
```

### Dry Run Mode
Want to see what FreshMint will do without making any changes? Use the `--dry-run` flag:
```bash
python3 freshmint.py --dry-run
```
*Output:*
```text
🧪  [DRY RUN] brew install 'git'
🧪  [DRY RUN] brew install 'curl'
🧪  [DRY RUN] pip3 install --user black flake8
```