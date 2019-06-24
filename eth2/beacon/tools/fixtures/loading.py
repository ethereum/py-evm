import os
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Tuple,
)

from eth_utils import (
    to_tuple,
)
from ruamel.yaml import (
    YAML,
    YAMLError,
)

from eth2.beacon.helpers import (
    compute_epoch_of_slot,
)
from eth2.configs import (
    Eth2Config,
)

from eth2.beacon.tools.fixtures.test_file import (
    TestFile,
)


#
# Eth2Config
#
def generate_config_by_dict(dict_config: Dict[str, Any]) -> Eth2Config:
    for key in list(dict_config):
        if 'DOMAIN_' in key:
            # DOMAIN is defined in SignatureDomain
            dict_config.pop(key, None)

    dict_config['GENESIS_EPOCH'] = compute_epoch_of_slot(
        dict_config['GENESIS_SLOT'],
        dict_config['SLOTS_PER_EPOCH'],
    )
    return Eth2Config(**dict_config)


def get_config(root_project_dir: Path, config_name: str) -> Eth2Config:
    # TODO: change the path after the constants presets are copied to submodule
    path = root_project_dir / 'tests/eth2/fixtures'
    yaml = YAML()
    file_name = config_name + '.yaml'
    file_to_open = path / file_name
    with open(file_to_open, 'U') as f:
        new_text = f.read()
        try:
            data = yaml.load(new_text)
        except YAMLError as exc:
            print(exc)
            raise
    return generate_config_by_dict(data)


def get_test_file_from_dict(data: Dict[str, Any],
                            root_project_dir: Path,
                            file_name: str,
                            parse_test_case_fn: Callable[..., Any]) -> TestFile:
    config_name = data['config']
    config = get_config(root_project_dir, config_name)
    parsed_test_cases = tuple(
        parse_test_case_fn(test_case, config)
        for test_case in data['test_cases']
    )
    return TestFile(
        file_name=file_name,
        config=config,
        test_cases=parsed_test_cases,
    )


@to_tuple
def get_files_of_dir(root_project_dir: Path,
                     path: Path,
                     parse_test_case_fn: Callable[..., Any]) -> Iterable[TestFile]:
    yaml = YAML()
    entries = os.listdir(path)
    for file_name in entries:
        # TODO: Now we only test minimal tests
        if 'minimal' in file_name:
            file_to_open = path / file_name
            with open(file_to_open, 'U') as f:
                new_text = f.read()
                try:
                    data = yaml.load(new_text)
                except YAMLError as exc:
                    print(exc)
                    raise
                test_file = get_test_file_from_dict(
                    data,
                    root_project_dir,
                    file_name,
                    parse_test_case_fn,
                )
                yield test_file


@to_tuple
def get_all_test_files(root_project_dir: Path,
                       fixture_pathes: Tuple[Path, ...],
                       parse_test_case_fn: Callable[..., Any]) -> Iterable[TestFile]:
    for path in fixture_pathes:
        yield from get_files_of_dir(root_project_dir, path, parse_test_case_fn)
