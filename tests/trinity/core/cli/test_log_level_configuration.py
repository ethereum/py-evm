import pytest

from trinity.cli_parser import (
    parser,
    LOG_LEVEL_CHOICES,
)


def test_cli_log_level_not_specified():
    ns = parser.parse_args([])
    assert ns.log_levels is None


@pytest.mark.parametrize(
    'level,expected',
    LOG_LEVEL_CHOICES.items(),
)
def test_cli_log_level_global_values(level, expected):
    ns = parser.parse_args(['--log-level', level])
    assert ns.log_levels == {None: expected}


@pytest.mark.parametrize(
    'level,expected',
    LOG_LEVEL_CHOICES.items(),
)
def test_cli_log_level_module_value(level, expected):
    ns = parser.parse_args(['--log-level', "module={0}".format(level)])
    assert ns.log_levels == {'module': expected}


def test_cli_log_level_error_for_multiple_globals(capsys):
    with pytest.raises(SystemExit):
        parser.parse_args([
            '--log-level', 'DEBUG',
            '--log-level', 'modue=DEBUG',
            '--log-level', 'ERROR',
        ])
    # this prevents the messaging that this error prints to stdout from
    # escaping the test run.
    capsys.readouterr()


def test_cli_log_level_error_for_repeated_name(capsys):
    with pytest.raises(SystemExit):
        parser.parse_args([
            '--log-level', 'DEBUG',
            '--log-level', 'modue_a=DEBUG',
            '--log-level', 'modue_b=DEBUG',
            '--log-level', 'modue_a=DEBUG',
        ])
    # this prevents the messaging that this error prints to stdout from
    # escaping the test run.
    capsys.readouterr()
