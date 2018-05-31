class BaseTrinityError(Exception):
    """
    The base class for all Trinity errors.
    """
    pass


class AmbigiousFileSystem(BaseTrinityError):
    """
    Raised when the file system paths are unclear
    """
    pass


class MissingPath(BaseTrinityError):
    """
    Raised when an expected path is missing
    """
    def __init__(self, msg, path):
        super(MissingPath, self).__init__(msg)
        self.path = path
