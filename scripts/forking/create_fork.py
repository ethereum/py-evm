import glob
from typing import NamedTuple
import pathlib
import shutil

SCRIPT_BASE_PATH = pathlib.Path(__file__).parent
SCRIPT_TEMPLATE_PATH = SCRIPT_BASE_PATH / 'template' / 'whitelabel'
ETH_BASE_PATH = SCRIPT_BASE_PATH.parent.parent / 'eth'
FORKS_BASE_PATH = ETH_BASE_PATH / 'vm' / 'forks'

INPUT_PROMPT = '-->'
YES = 'y'

# Given a fork name of Muir Glacier we need to derive:
# pascal case: MuirGlacier
# lower_dash_case: muir-glacier
# lower_snake_case: muir_glacier
# upper_snake_case: MUIR_GLACIER


class Writing(NamedTuple):
    pascal_case: str
    lower_dash_case: str
    lower_snake_case: str
    upper_snake_case: str


WHITELABEL_FORK = Writing(
    pascal_case="Istanbul",
    lower_dash_case="istanbul",
    lower_snake_case="istanbul",
    upper_snake_case="ISTANBUL",
)

WHITELABEL_PARENT = Writing(
    pascal_case="Petersburg",
    lower_dash_case="petersburg",
    lower_snake_case="petersburg",
    upper_snake_case="PETERSBURG",
)


def bootstrap() -> None:
    print("Specify the name of the fork (e.g Muir Glacier):")
    fork_name = input(INPUT_PROMPT)

    if not all(x.isalpha() or x.isspace() for x in fork_name):
        print(f"Can't use {fork_name} as fork name, must be alphabetical")
        return

    print("Specify the fork base (e.g Istanbul):")
    fork_base = input(INPUT_PROMPT)

    writing_new_fork = create_writing(fork_name)
    writing_parent_fork = create_writing(fork_base)

    fork_base_path = FORKS_BASE_PATH / writing_parent_fork.lower_snake_case
    if not fork_base_path.exists():
        print(f"No fork exists at {fork_base_path}")
        return

    print("Check your inputs:")
    print("New fork:")
    print(writing_new_fork)

    print("Base fork:")
    print(writing_parent_fork)

    print("Proceed (y/n)?")
    proceed = input(INPUT_PROMPT)

    if proceed.lower() == YES:
        create_fork(writing_new_fork, writing_parent_fork)
        print("Your fork is ready!")


def create_writing(fork_name: str):
    # Remove extra spaces
    normalized = " ".join(fork_name.split())

    snake_case = normalized.replace(' ', '_')
    dash_case = normalized.replace(' ', '-')
    pascal_case = normalized.title().replace(' ', '')

    return Writing(
        pascal_case=pascal_case,
        lower_dash_case=dash_case.lower(),
        lower_snake_case=snake_case.lower(),
        upper_snake_case=snake_case.upper(),
    )


def create_fork(writing_new_fork: Writing, writing_parent_fork: Writing) -> None:
    fork_path = FORKS_BASE_PATH / writing_new_fork.lower_snake_case
    shutil.copytree(SCRIPT_TEMPLATE_PATH, fork_path)
    replace_in(fork_path, WHITELABEL_FORK.pascal_case, writing_new_fork.pascal_case)
    replace_in(fork_path, WHITELABEL_FORK.lower_snake_case, writing_new_fork.lower_snake_case)
    replace_in(fork_path, WHITELABEL_FORK.lower_dash_case, writing_new_fork.lower_dash_case)
    replace_in(fork_path, WHITELABEL_FORK.upper_snake_case, writing_new_fork.upper_snake_case)

    replace_in(fork_path, WHITELABEL_PARENT.pascal_case, writing_parent_fork.pascal_case)
    replace_in(fork_path, WHITELABEL_PARENT.lower_snake_case, writing_parent_fork.lower_snake_case)
    replace_in(fork_path, WHITELABEL_PARENT.lower_dash_case, writing_parent_fork.lower_dash_case)
    replace_in(fork_path, WHITELABEL_PARENT.upper_snake_case, writing_parent_fork.upper_snake_case)


def replace_in(base_path: pathlib.Path, find_text: str, replace_txt: str) -> None:
    for filepath in glob.iglob(f'{base_path}/**/*.py', recursive=True):
        with open(filepath) as file:
            s = file.read()
        s = s.replace(find_text, replace_txt)
        with open(filepath, "w") as file:
            file.write(s)


if __name__ == '__main__':
    bootstrap()
