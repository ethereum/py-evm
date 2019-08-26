from typing import NewType


ConfigName = NewType("ConfigName", str)

Mainnet = "mainnet"
Minimal = "minimal"

ALL_CONFIG_NAMES = (Mainnet, Minimal)
ONLY_MINIMAL = (Minimal,)
