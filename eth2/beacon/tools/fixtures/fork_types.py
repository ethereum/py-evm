import abc


class ForkType(abc.ABC):
    name: str


class Phase0(ForkType):
    name = "phase0"
