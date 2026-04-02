import copy
import os
import subprocess
import sys

from testing_utils import empty_test


def test_blender_cli_arguments_propagation(testing_context):
    """CLI arguments propagation."""
    with testing_context(
        {
            "tests/test_blender_argv.py": """
import sys

def test_blender_argv():
    assert '--debug' in sys.argv
"""
        }
    ) as ctx:
        stdout, stderr, exitcode = ctx.run(["--", "--debug"])
        assert exitcode == 0, stderr

        # Blender debugging information with `--debug`
        assert "argv[2] = --debug" in stdout, stderr


def test_blender_cli_args_pass_through_with_separator(tmp_path):
    """
    Verify that pytest-blender correctly handles CLI arguments passed after the
    '--' (End of Options) separator.

    Specifically, this test ensures that arguments like '--python-use-system-env',
    which are intended for Blender, are not mistakenly parsed by Pytest as positional
    file/directory arguments or unrecognized options when placed after '--'.
    """
    # --- Test Environment Setup ---
    rootdir = tmp_path / "blender_test_proj"
    rootdir.mkdir()

    # Create pytest.ini to enable pytest-blender configuration
    ini = rootdir / "pytest.ini"
    ini.write_text("""
[pytest]
pytest-blender-debug=true
""")

    # Create tests directory and test file
    tests_dir = rootdir / "tests"
    tests_dir.mkdir()

    test_file = tests_dir / "test_blender_integration.py"
    test_file.write_text("""
def test_blender_env_check(pytestconfig):
    '''
    A simple placeholder test to ensure the session runs.
    The primary verification happens in conftest and via CLI output checks.
    '''
    import os
    assert os.path.exists(__file__)
""")

    # Create conftest.py for hook-based validation
    conftest = tests_dir / "conftest.py"
    conftest.write_text("""
import pytest

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # Stage 1 check: Ensure '--' arguments are filtered out by Pytest.
    # 'no:pytest-blender' is present only in Stage 2 (inside Blender), so its absence confirms Stage 1.
    if "no:pytest-blender" not in config.invocation_params.args:
        assert [] == config.option.file_or_dir, \
            "Expected empty file_or_dir in Stage 1; args after '--' were passed as plugin-specific arguments."
""")

    # --- Command Execution ---
    # Construct command with '--' to separate pytest options from Blender arguments
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-svv",  # Verbose output
        "--",  # End of Options: Everything after this is treated as plugin-specific
        "--python-use-system-env",  # Argument intended for Blender, not pytest
    ]

    # Prepare environment to ensure isolation from host system's PWD
    env = copy.deepcopy(os.environ)
    if "PWD" in env:
        del env["PWD"]
    env["PWD"] = str(rootdir)

    print(f"Running command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(rootdir), env=env
    )

    stdout = result.stdout
    stderr = result.stderr
    exit_code = result.returncode

    # --- Assertions ---

    # Ensure the process exited successfully (exit code 0)
    if exit_code != 0:
        print(f"STDOUT:\n{stdout}")
        print(f"STDERR:\n{stderr}")

    assert exit_code == 0, f"pytest failed to run successfully. STDERR:\\n{stderr}"

    # CLI arguments propagate to blender_opts
    assert "-b --python-use-system-env --python" in stdout, (
        f"cli arguments propagation failed. STDOUT:\\n{stdout}"
    )
    print(stdout, stderr)


def test_cli_env_propagation(testing_context):
    """Environment variables propagation."""
    custom_pyc_files_dirname = "custom_pyc_files_dir"
    with testing_context(
        {
            "tests/test_python_cache_prefix.py": f"""
import os
import sys

def test_python_cache_prefix():
    python_cache_prefix = os.environ.get("PYTHONPYCACHEPREFIX")
    assert os.path.basename(python_cache_prefix) == "{custom_pyc_files_dirname}"
    sys.stdout.write(python_cache_prefix + '\\n')
""",
            os.path.join(custom_pyc_files_dirname, "empty.txt"): "",
        }
    ) as ctx:
        custom_pyc_files_dir = os.path.join(ctx.rootdir, custom_pyc_files_dirname)
        stdout, stderr, exitcode = ctx.run(
            env={"PYTHONPYCACHEPREFIX": custom_pyc_files_dir},
        )
        msg = f"{stdout}\n---\n{stderr}\n"
        assert exitcode == 0, msg
        assert custom_pyc_files_dir in stdout

        # pyc files directories added
        assert len(custom_pyc_files_dir) > 1


def test_enable_plugin_explicitly_from_pytest_cli(testing_context):
    with testing_context(
        {
            "tests/test_no_explicit_enabling.py": """
import sys

def test_no_explicit_pytest_blender_plugin_enabling():
    assert '-p' not in sys.argv
    assert 'pytest-blender' not in sys.argv
""",
        }
    ) as ctx:
        # if we explicitly enable pytest-blender using `-p pytest-blender`
        # the tests itself are tried to be executed with pytest-blender
        # which could result in a infinite loop, but is not the case because
        # the arguments are malformed in the second execution
        #
        # the solution here is to remove the invalid argument in the Blender
        # execution at `plugin.py`
        stdout, stderr, exitcode = ctx.run(
            ["-p", "pytest-blender", "--pytest-blender-debug"]
        )
        assert exitcode == 0, stderr
        assert "-p pytest-blender" not in stdout


def test_pytest_help(testing_context):
    with testing_context({"tests/test_foo.py": empty_test}) as ctx:
        stdout, stderr, exitcode = ctx.run(["-h"])
        assert stdout.startswith("usage:")
        assert exitcode == 0, f"{stdout}\n----\n{stderr}"
