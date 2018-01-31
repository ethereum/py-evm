class Configurable(object):
    """
    Base class for simple inline subclassing
    """
    @classmethod
    def configure(cls,
                  name=None,
                  **overrides):

        if name is None:
            name = cls.__name__

        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The {0}.configure cannot set attributes that are not "
                    "already present on the base class. The attribute `{1}` was "
                    "not found on the base class `{2}`".format(cls.__name__, key, cls)
                )

        return type(name, (cls,), overrides)
