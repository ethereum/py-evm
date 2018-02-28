class WitnessPackage:
    def __init__(
            self,
            coinbase,
            coinbase_witness,
            transaction_packages):
        self.coinbase = coinbase
        self.coinbase_witness = coinbase_witness
        self.transaction_packages = transaction_packages
