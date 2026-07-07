"""
Test suite for FreshMint.

Nothing here ever touches your real system. subprocess.run, shutil.which,
and input() are all mocked at the boundary, so no package manager, no
Homebrew installer, and no VS Code CLI is ever actually invoked.

Run with:
    pytest test_freshmint.py -v
"""

import subprocess

import pytest

import freshmint


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------

def test_run_command_dry_run_does_not_execute(capsys, mocker):
    mock_run = mocker.patch("subprocess.run")
    result = freshmint.run_command(["brew", "install", "git"], dry_run=True)

    assert result is True
    mock_run.assert_not_called()
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "brew install git" in captured.out


def test_run_command_dry_run_quotes_special_chars(capsys):
    freshmint.run_command(["echo", "hello world"], dry_run=True)
    captured = capsys.readouterr()
    # shlex.join should quote the argument containing a space
    assert "'hello world'" in captured.out


def test_run_command_success(mocker):
    mock_run = mocker.patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0),
    )
    result = freshmint.run_command(["echo", "hi"], dry_run=False)

    assert result is True
    mock_run.assert_called_once()


def test_run_command_called_process_error(mocker, capsys):
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd="fake-cmd", stderr="boom"
        ),
    )
    result = freshmint.run_command(["fake-cmd"], dry_run=False)

    assert result is False
    captured = capsys.readouterr()
    assert "boom" in captured.err


def test_run_command_file_not_found(mocker, capsys):
    mocker.patch("subprocess.run", side_effect=FileNotFoundError())
    result = freshmint.run_command(["nonexistent-binary"], dry_run=False)

    assert result is False
    captured = capsys.readouterr()
    assert "Command not found" in captured.err


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def test_load_config_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        freshmint.load_config(str(tmp_path / "nope.yaml"))


def test_load_config_empty_file(tmp_path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    with pytest.raises(SystemExit):
        freshmint.load_config(str(f))


def test_load_config_non_dict_yaml(tmp_path):
    # Valid YAML, but a top-level list instead of a dict
    f = tmp_path / "list.yaml"
    f.write_text("- git\n- curl\n")
    with pytest.raises(SystemExit):
        freshmint.load_config(str(f))


def test_load_config_malformed_yaml(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("key: [unclosed")
    with pytest.raises(SystemExit):
        freshmint.load_config(str(f))


def test_load_config_valid_yaml(tmp_path):
    f = tmp_path / "good.yaml"
    f.write_text("system_packages:\n  linux:\n    - git\n")
    config = freshmint.load_config(str(f))

    assert isinstance(config, dict)
    assert config["system_packages"]["linux"] == ["git"]


# ---------------------------------------------------------------------------
# detect_os
# ---------------------------------------------------------------------------

def test_detect_os_macos(mocker):
    mocker.patch("platform.system", return_value="Darwin")
    assert freshmint.detect_os() == "macos"


def test_detect_os_linux(mocker):
    mocker.patch("platform.system", return_value="Linux")
    assert freshmint.detect_os() == "linux"


def test_detect_os_unsupported(mocker):
    mocker.patch("platform.system", return_value="Windows")
    with pytest.raises(SystemExit):
        freshmint.detect_os()


# ---------------------------------------------------------------------------
# check_command_exists
# ---------------------------------------------------------------------------

def test_check_command_exists_true(mocker):
    mocker.patch("shutil.which", return_value="/usr/bin/git")
    assert freshmint.check_command_exists("git") is True


def test_check_command_exists_false(mocker):
    mocker.patch("shutil.which", return_value=None)
    assert freshmint.check_command_exists("nonexistent-tool") is False


# ---------------------------------------------------------------------------
# ensure_homebrew
# ---------------------------------------------------------------------------

def test_ensure_homebrew_already_installed(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=True)
    assert freshmint.ensure_homebrew(dry_run=False) is True


def test_ensure_homebrew_dry_run_when_missing(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    # Should return True in dry-run so downstream package preview still runs
    assert freshmint.ensure_homebrew(dry_run=True) is True


def test_ensure_homebrew_user_declines(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    mocker.patch("builtins.input", return_value="n")
    assert freshmint.ensure_homebrew(dry_run=False) is False


def test_ensure_homebrew_user_accepts_and_succeeds(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    mocker.patch("builtins.input", return_value="y")
    mocker.patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0),
    )
    result = freshmint.ensure_homebrew(dry_run=False)
    assert result is True


def test_ensure_homebrew_user_accepts_but_install_fails(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    mocker.patch("builtins.input", return_value="y")
    mocker.patch(
        "subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=1),
    )
    result = freshmint.ensure_homebrew(dry_run=False)
    assert result is False


def test_ensure_homebrew_keyboard_interrupt(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    mocker.patch("builtins.input", side_effect=KeyboardInterrupt())
    result = freshmint.ensure_homebrew(dry_run=False)
    assert result is False


# ---------------------------------------------------------------------------
# install_system_packages
# ---------------------------------------------------------------------------

def test_install_system_packages_no_section_for_os(mocker, capsys):
    mock_run_cmd = mocker.patch("freshmint.run_command")
    freshmint.install_system_packages(
        {"system_packages": {"linux": ["git"]}}, "macos", dry_run=False
    )
    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "No system packages defined" in captured.err


def test_install_system_packages_empty_list(mocker, capsys):
    mock_run_cmd = mocker.patch("freshmint.run_command")
    freshmint.install_system_packages(
        {"system_packages": {"linux": []}}, "linux", dry_run=False
    )
    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "empty" in captured.err.lower()


def test_install_system_packages_macos_installs_individually(mocker):
    mocker.patch("freshmint.ensure_homebrew", return_value=True)
    mock_run_cmd = mocker.patch("freshmint.run_command", return_value=True)

    config = {"system_packages": {"macos": ["git", "curl", "zsh"]}}
    freshmint.install_system_packages(config, "macos", dry_run=False)

    # One brew install call per package
    assert mock_run_cmd.call_count == 3
    called_packages = [call.args[0][-1] for call in mock_run_cmd.call_args_list]
    assert called_packages == ["git", "curl", "zsh"]


def test_install_system_packages_macos_no_homebrew(mocker, capsys):
    mocker.patch("freshmint.ensure_homebrew", return_value=False)
    mock_run_cmd = mocker.patch("freshmint.run_command")

    config = {"system_packages": {"macos": ["git"]}}
    freshmint.install_system_packages(config, "macos", dry_run=False)

    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "Cannot install macOS packages" in captured.err


def test_install_system_packages_linux_batches(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=True)
    mock_run_cmd = mocker.patch("freshmint.run_command", return_value=True)

    config = {"system_packages": {"linux": ["git", "curl"]}}
    freshmint.install_system_packages(config, "linux", dry_run=False)

    # 1 call for "apt update" + 1 batched call for "apt install -y git curl"
    assert mock_run_cmd.call_count == 2
    install_call_args = mock_run_cmd.call_args_list[-1].args[0]
    assert install_call_args == ["sudo", "apt", "install", "-y", "git", "curl"]


def test_install_system_packages_linux_no_apt(mocker, capsys):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    mock_run_cmd = mocker.patch("freshmint.run_command")

    config = {"system_packages": {"linux": ["git"]}}
    freshmint.install_system_packages(config, "linux", dry_run=False)

    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "Apt package manager not found" in captured.err


# ---------------------------------------------------------------------------
# install_python_packages
# ---------------------------------------------------------------------------

def test_install_python_packages_none_defined(mocker, capsys):
    mock_run_cmd = mocker.patch("freshmint.run_command")
    freshmint.install_python_packages({}, dry_run=False)
    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "No Python packages defined" in captured.err


def test_install_python_packages_no_pip3(mocker, capsys):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    mock_run_cmd = mocker.patch("freshmint.run_command")

    config = {"python_packages": ["black", "flake8"]}
    freshmint.install_python_packages(config, dry_run=False)

    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "pip3" in captured.err


def test_install_python_packages_upgrade_failure_is_non_fatal(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=True)
    # First call (pip upgrade) fails, second call (batched install) succeeds
    mock_run_cmd = mocker.patch(
        "freshmint.run_command", side_effect=[False, True]
    )

    config = {"python_packages": ["black"]}
    freshmint.install_python_packages(config, dry_run=False)

    assert mock_run_cmd.call_count == 2
    # The batched install must still be attempted despite the upgrade failing
    install_call_args = mock_run_cmd.call_args_list[-1].args[0]
    assert install_call_args == ["pip3", "install", "--user", "black"]


def test_install_python_packages_batches_all(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=True)
    mock_run_cmd = mocker.patch("freshmint.run_command", return_value=True)

    config = {"python_packages": ["black", "flake8", "isort"]}
    freshmint.install_python_packages(config, dry_run=False)

    install_call_args = mock_run_cmd.call_args_list[-1].args[0]
    assert install_call_args == [
        "pip3", "install", "--user", "black", "flake8", "isort",
    ]


# ---------------------------------------------------------------------------
# install_vscode_extensions
# ---------------------------------------------------------------------------

def test_install_vscode_extensions_none_defined(mocker, capsys):
    mock_run_cmd = mocker.patch("freshmint.run_command")
    freshmint.install_vscode_extensions({}, dry_run=False)
    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "No VS Code extensions defined" in captured.err


def test_install_vscode_extensions_no_code_cli(mocker, capsys):
    mocker.patch("freshmint.check_command_exists", return_value=False)
    mock_run_cmd = mocker.patch("freshmint.run_command")

    config = {"vscode_extensions": ["ms-python.python"]}
    freshmint.install_vscode_extensions(config, dry_run=False)

    mock_run_cmd.assert_not_called()
    captured = capsys.readouterr()
    assert "code" in captured.err.lower()


def test_install_vscode_extensions_installs_individually(mocker):
    mocker.patch("freshmint.check_command_exists", return_value=True)
    mock_run_cmd = mocker.patch("freshmint.run_command", return_value=True)

    config = {"vscode_extensions": ["ms-python.python", "esbenp.prettier-vscode"]}
    freshmint.install_vscode_extensions(config, dry_run=False)

    assert mock_run_cmd.call_count == 2
    called_extensions = [call.args[0][-1] for call in mock_run_cmd.call_args_list]
    assert called_extensions == ["ms-python.python", "esbenp.prettier-vscode"]


# ---------------------------------------------------------------------------
# Integration-style test: full config, dry-run, no mocking of run_command
# (only the environment-detection calls are mocked so this runs anywhere)
# ---------------------------------------------------------------------------

def test_full_dry_run_pipeline_end_to_end(mocker, tmp_path, capsys):
    mocker.patch("freshmint.check_command_exists", return_value=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
system_packages:
  linux:
    - git
python_packages:
  - black
vscode_extensions:
  - ms-python.python
"""
    )

    config = freshmint.load_config(str(config_path))
    freshmint.install_system_packages(config, "linux", dry_run=True)
    freshmint.install_python_packages(config, dry_run=True)
    freshmint.install_vscode_extensions(config, dry_run=True)

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "git" in captured.out
    assert "black" in captured.out
    assert "ms-python.python" in captured.out