"""
This is a script to fill EEST tests from the ``execution-spec-tests`` repository. In
order to run this script, you need to have the `execution-spec-tests` repository cloned
and set up, as per the README.md in the repository.

Make sure your git history is up to date
and that your working directory is clean, as this script attempts to ``git checkout``
the branch specified in the `--branch` flag, pull in the latest changes, and then fill
the tests.

Note: `pytest-xdist` is required to run this script.

Running the script to fill EEST tests:

  - From the root of the `py-evm` repository, run the following command:
    ``python scripts/fill_eest_tests.py``

Args:
----
    --execution-spec-tests-dir: Path to execution-spec-tests directory, defaults to
      "../execution-spec-tests".

    --branch: Branch to fill tests from, defaults to "main".

    --until: Fork name to fill tests up to, defaults to "Cancun".

    --fork: Fork name to fill tests for. (will override the --until flag)

    -k: `k` arg to pass through to EEST / pytest.

    -n: (int) Number of processes to use to fill tests, defaults to 1.


Example:
-------

    ``python scripts/fill_eest_tests.py --execution-spec-tests-dir="../execution-spec-tests" --branch="pectra-devnet-5" --until="Prague" -n 4``  # noqa: E501

"""

import argparse
import os

cwd = os.getcwd()

parser = argparse.ArgumentParser(description="Fill EEST tests")
parser.add_argument(
    "--execution-spec-tests-dir",
    type=str,
    dest="execution_spec_tests_dir",
    default="../execution-spec-tests",
    help="Path to execution-spec-tests directory.",
)
parser.add_argument(
    "--branch",
    type=str,
    dest="branch",
    default="main",
    help="Branch to fill tests from. Defaults to `main`.",
)
parser.add_argument(
    "--until",
    type=str,
    dest="until_fork",
    default="Cancun",
    help='Fork name to fill tests up to. Defaults to "Cancun".',
)
parser.add_argument(
    "--fork",
    type=str,
    dest="fork",
    default=None,
    help="Fork name to fill tests for.",
)
parser.add_argument(
    "-k",
    type=str,
    dest="k_args",
    default=None,
    help="`k` arg to pass through to EEST / pytest.",
)
parser.add_argument(
    "-n",
    type=int,
    dest="num_processes",
    default=None,
    help="Number of processes to use to fill tests.",
)
parser.add_argument(
    "-m",
    type=str,
    dest="m_args",
    default="not slow",
    help="`m` arg to pass through to EEST / pytest.",
)

args = parser.parse_args()


# change working directory to `execution-spec-tests` and fill tests
os.chdir(args.execution_spec_tests_dir)

# ``uv.lock`` is always altered locally but rarely committed by outside contributors
# assume that it may have been altered and reset before attempting to ``checkout``
os.system("git checkout uv.lock")
os.system(f"git fetch && git checkout {args.branch} && git pull")

fork_command = f"--fork={args.fork}" if args.fork else f"--until={args.until_fork}"
m_command = f'-m "{args.m_args}"' if args.m_args else ""

# build fill command
command = f'uv run fill {fork_command} {m_command} --output="{cwd}/fixtures_eest"'
if args.k_args:
    command += f" -k {args.k_args}"
if args.num_processes:
    command += f" -n {args.num_processes}"

# fill tests
print(f"Running `{command}`")
os.system(command)
