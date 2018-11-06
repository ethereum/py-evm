from trinity.extensibility.plugin import BaseIsolatedPlugin


class TestPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return "TestPlugin"
