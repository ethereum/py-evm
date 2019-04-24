from pathlib import Path

from trinity.config import (
    TrinityConfig,
)


def get_networkdb_path(config: TrinityConfig) -> Path:
    base_db_path = config.with_app_suffix(
        config.data_dir / "networkdb"
    )
    return base_db_path.with_name(base_db_path.name + ".sqlite3")
