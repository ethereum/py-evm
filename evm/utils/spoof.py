class SpoofAttributes:
    def __init__(self, spoof_target, **overrides):
        self.spoof_target = spoof_target
        self.overrides = overrides

    def __getattr__(self, attr):
        if attr in self.overrides:
            return self.overrides[attr]
        else:
            return getattr(self.spoof_target, attr)


class SpoofTransaction(SpoofAttributes):
    def __init__(self, transaction, **overrides):
        if 'get_sender' not in overrides:
            current_sender = transaction.get_sender()
            overrides['get_sender'] = lambda: current_sender
        super().__init__(transaction, **overrides)
