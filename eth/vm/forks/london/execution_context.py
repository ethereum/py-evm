from eth.abc import ExecutionContextAPI


class LondonExecutionContext(ExecutionContextAPI):
    def __init__(self, base_gas_fee: int, **kwargs): # TODO remove kwargs
        super().__init__(**kwargs)
        self._base_gas_fee = base_gas_fee