class MockTransport:
    def __init__(self):
        self._is_closing = False

    def close(self):
        self._is_closing = True

    def is_closing(self):
        return self._is_closing


class MockStreamWriter:
    def __init__(self, write_target):
        self._target = write_target
        self.transport = MockTransport()

    def write(self, *args, **kwargs):
        self._target(*args, **kwargs)

    def close(self):
        self.transport.close()
