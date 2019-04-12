from eth.vm.forks.constantinople.state import (
    ConstantinopleState
)

from .computation import IstanbulComputation


class IstanbulState(ConstantinopleState):
    computation_class = IstanbulComputation
