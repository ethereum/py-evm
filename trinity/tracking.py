from argparse import (
    Namespace,
)
import logging
from pathlib import Path

from trinity.config import (
    TrinityConfig,
)


logger = logging.getLogger('trinity.tracking')


def get_nodedb_path(config: TrinityConfig) -> Path:
    base_db_path = config.with_app_suffix(
        config.data_dir / "nodedb"
    )
    return base_db_path.with_name(base_db_path.name + ".sqlite3")


def clear_node_db(args: Namespace, trinity_config: TrinityConfig) -> None:
    db_path = get_nodedb_path(trinity_config)

    if db_path.exists():
        logger.info("Removing node database at: %s", db_path.resolve())
        db_path.unlink()
    else:
        logger.info("No node database found at: %s", db_path.resolve())
