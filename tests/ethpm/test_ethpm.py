import pytest
from ethpm import Package
from evm.exceptions import ValidationError
from jsonschema import ValidationError as VE2


def test_ethpm_exists():
    assert Package


@pytest.fixture()
def valid_package():
    return "./tests/ethpm/validSample.json"


@pytest.fixture()
def invalid_package():
    return "./tests/ethpm/invalidSample.json"


def test_ethpm_instantiates_with_valid_package(valid_package):
    current_package = Package(valid_package)
    assert current_package.package_identifier == valid_package
    assert current_package.parsed_json


def test_ethpm_doesnt_instantiate_with_invalid_package(invalid_package):
    with pytest.raises(VE2):
        Package(invalid_package)


@pytest.mark.parametrize(
    "invalid_path",
    (
        "./tests/ethpm/doesntExist.json",
        12345,
        "abcd",
    )
)
def test_ethpm_doesnt_instantiate_with_invalid_path(invalid_path):
    with pytest.raises(ValidationError):
        Package(invalid_path)
