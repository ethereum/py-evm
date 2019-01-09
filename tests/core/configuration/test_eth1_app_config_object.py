import pytest

from trinity.config import (
    Eth1AppConfig,
    TrinityConfig,
)
from trinity.nodes.full import (
    FullNode,
)
from trinity.nodes.light import (
    LightNode,
)


@pytest.mark.parametrize(
    "app_identifier, sync_mode, expected_db_path, expected_db_name",
    (
        ("beacon", "light", "chain-beacon", "light"),
        ("beacon", "fast", "chain-beacon", "full"),
        ("eth1", "light", "chain-eth1", "light"),
        ("eth1", "fast", "chain-eth1", "full"),
        ("", "light", "chain", "light"),
        ("", "fast", "chain", "full"),
    ),
)
def test_computed_database_dir(app_identifier, sync_mode, expected_db_path, expected_db_name):
    trinity_config = TrinityConfig(network_id=1, app_identifier=app_identifier)
    eth1_app_config = Eth1AppConfig(trinity_config, sync_mode)

    assert eth1_app_config.database_dir == trinity_config.data_dir / expected_db_path / expected_db_name  # noqa: E501


@pytest.mark.parametrize(
    "sync_mode, expected_full_db, expected_node_class",
    (
        ("light", False, LightNode),
        ("fast", True, FullNode),
        ("full", True, FullNode),
        ("warp", True, FullNode),
    ),
)
def test_sync_mode_effect_on_db_and_node_type(sync_mode,
                                              expected_full_db,
                                              expected_node_class):

    trinity_config = TrinityConfig(network_id=1)
    eth1_app_config = Eth1AppConfig(trinity_config, sync_mode)
    assert eth1_app_config.sync_mode == sync_mode
    assert eth1_app_config.node_class == expected_node_class
    assert eth1_app_config.uses_full_db is expected_full_db
    assert eth1_app_config.uses_light_db is not expected_full_db
