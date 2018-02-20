from cytoolz import (
    assoc,
    groupby,
)

from eth_utils import (
    to_dict,
    to_set,
)


def _is_local_prop(prop):
    return len(prop.split('.')) == 1


def _extract_top_level_key(prop):
    left, _, _ = prop.partition('.')
    return left


def _extract_tail_key(prop):
    _, _, right = prop.partition('.')
    return right


@to_dict
def _get_local_overrides(overrides):
    for prop, value in overrides.items():
        if _is_local_prop(prop):
            yield prop, value


@to_dict
def _get_sub_overrides(overrides):
    for prop, value in overrides.items():
        if not _is_local_prop(prop):
            yield prop, value


@to_dict
def _get_sub_overrides_by_prop(overrides):
    # we only want the overrides that are not top level.
    sub_overrides = _get_sub_overrides(overrides)
    key_groups = groupby(_extract_top_level_key, sub_overrides.keys())
    for top_level_key, props in key_groups.items():
        yield top_level_key, {_extract_tail_key(prop): overrides[prop] for prop in props}


@to_set
def _get_top_level_keys(overrides):
    for prop in overrides:
        yield _extract_top_level_key(prop)


class Configurable(object):
    """
    Base class for simple inline subclassing
    """
    @classmethod
    def configure(cls,
                  __name__=None,
                  **overrides):

        if __name__ is None:
            __name__ = cls.__name__

        top_level_keys = _get_top_level_keys(overrides)

        # overrides that are *local* to this class.
        local_overrides = _get_local_overrides(overrides)

        for key in top_level_keys:
            if key == '__name__':
                continue
            elif not hasattr(cls, key):
                raise TypeError(
                    "The {0}.configure cannot set attributes that are not "
                    "already present on the base class. The attribute `{1}` was "
                    "not found on the base class `{2}`".format(cls.__name__, key, cls)
                )

        # overrides that are for sub-properties of this class
        sub_overrides_by_prop = _get_sub_overrides_by_prop(overrides)

        for key, sub_overrides in sub_overrides_by_prop.items():
            if key in local_overrides:
                sub_cls = local_overrides[key]
            elif hasattr(cls, key):
                sub_cls = getattr(cls, key)
            else:
                raise Exception(
                    "Invariant: the pre-check that all top level keys are "
                    "present on `cls` should make this code path unreachable"
                )

            if not isinstance(sub_cls, type) or not issubclass(sub_cls, Configurable):
                raise TypeError(
                    "Unable to configure property `{0}` on class `{1}`.  The "
                    "property being configured must be a subclass of the "
                    "`Configurable` type.  Instead got the following object "
                    "instance: {2}".format(
                        key,
                        repr(cls),
                        repr(sub_cls),
                    )
                )

            configured_sub_cls = sub_cls.configure(**sub_overrides)
            local_overrides = assoc(local_overrides, key, configured_sub_cls)

        return type(__name__, (cls,), local_overrides)
