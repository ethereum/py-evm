import os
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Sequence,
    Tuple,
)

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    assoc,
    keyfilter,
)
from ruamel.yaml import (
    YAML,
)

from eth2.beacon.helpers import (
    compute_epoch_of_slot,
)
from eth2.configs import (
    Eth2Config,
)

from eth2.beacon.tools.fixtures.config_name import (
    ALL_CONFIG_NAMES,
    ConfigName,
)
from eth2.beacon.tools.fixtures.test_file import (
    TestFile,
)


#
# Eth2Config
#
def generate_config_by_dict(dict_config: Dict[str, Any]) -> Eth2Config:
    config_without_domains = keyfilter(lambda name: "DOMAIN_" not in name, dict_config)

    return Eth2Config(
        **assoc(
            config_without_domains,
            "GENESIS_EPOCH",
            compute_epoch_of_slot(
                dict_config['GENESIS_SLOT'],
                dict_config['SLOTS_PER_EPOCH'],
            )
        )
    )


config_cache: Dict[str, Eth2Config] = {}


def get_config(root_project_dir: Path, config_name: ConfigName) -> Eth2Config:
    if config_name in config_cache:
        return config_cache[config_name]

    # TODO: change the path after the constants presets are copied to submodule
    path = root_project_dir / 'tests/eth2/fixtures'
    yaml = YAML()
    file_name = config_name + '.yaml'
    file_to_open = path / file_name
    with open(file_to_open, 'U') as f:
        new_text = f.read()
        data = yaml.load(new_text)
    config = generate_config_by_dict(data)
    config_cache[config_name] = config
    return config


def get_test_file_from_dict(data: Dict[str, Any],
                            root_project_dir: Path,
                            file_name: str,
                            parse_test_case_fn: Callable[..., Any]) -> TestFile:
    config_name = data['config']
    assert config_name in ALL_CONFIG_NAMES
    config_name = ConfigName(config_name)
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
                     config_names: Sequence[ConfigName],
                     parse_test_case_fn: Callable[..., Any]) -> Iterable[TestFile]:
    yaml = YAML()
    entries = os.listdir(path)
    for file_name in entries:
        for config_name in config_names:
            if config_name in file_name:
                file_to_open = path / file_name
                with open(file_to_open, 'U') as f:
                    new_text = f.read()
                    data = yaml.load(new_text)
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
                       config_names: Sequence[ConfigName],
                       parse_test_case_fn: Callable[..., Any]) -> Iterable[TestFile]:
    for path in fixture_pathes:
        yield from get_files_of_dir(root_project_dir, path, config_names, parse_test_case_fn)
