import pytest

from eth._utils.datatypes import (
    Configurable,
)


class Inner(Configurable):
    attr_a = "original-a"
    attr_b = "original-b"


class NonConfigurable:
    attr_x = "original-x"


class Outer(Configurable):
    attr_c = "original-c"
    attr_d = "original-d"

    attr_e = Inner
    attr_f = None
    attr_g = None
    attr_h = NonConfigurable
    attr_j = Inner()
    attr_k = None


def test_single_layer_configuration():
    result = Inner.configure(
        attr_a="configured-a",
    )
    assert result.attr_a == "configured-a"
    assert result.attr_b == "original-b"


def test_positional_name_configuration():
    result = Inner.configure(
        "ConfiguredInner",
        attr_a="configured-a",
    )
    assert result.__name__ == "ConfiguredInner"
    assert result.attr_a == "configured-a"


def test_keyword_name_configuration():
    result = Inner.configure(
        __name__="ConfiguredInner",
        attr_a="configured-a",
    )
    assert result.__name__ == "ConfiguredInner"
    assert result.attr_a == "configured-a"


def test_sub_name_configuration():
    result = Outer.configure(
        **{
            "attr_e.__name__": "ConfiguredInner",
            "attr_e.attr_a": "configured-a",
        }
    )
    assert result.attr_e.__name__ == "ConfiguredInner"
    assert result.attr_e.attr_a == "configured-a"


def test_sub_property_configuration():
    result = Outer.configure(
        "ConfiguredOuter",
        attr_c="configured-c",
        **{
            "attr_e.attr_a": "configured-a",
            "attr_f": Inner,
            "attr_f.attr_b": "configured-b",
            "attr_g": Inner,
            "attr_k": NonConfigurable,
        }
    )

    assert result.attr_c == "configured-c"
    assert result.attr_d == "original-d"

    assert result.attr_e is not Inner
    assert issubclass(result.attr_e, Inner)
    assert result.attr_e.attr_a == "configured-a"
    assert result.attr_e.attr_b == "original-b"

    assert result.attr_f is not Inner
    assert issubclass(result.attr_f, Inner)
    assert result.attr_f.attr_a == "original-a"
    assert result.attr_f.attr_b == "configured-b"

    assert result.attr_g is Inner

    assert result.attr_k is NonConfigurable


@pytest.mark.parametrize(
    "key",
    (
        "top_level",
        "top_level.nested_level",
    ),
)
def test_error_if_attr_not_present_at_top_level(key):
    with pytest.raises(TypeError):
        Inner.configure(**{key: "value"})


def test_error_if_attr_not_present_in_sub_obj():
    with pytest.raises(TypeError):
        Outer.configure(**{"attr_e.not_present": "value"})


def test_error_trying_to_configure_non_configurable_class():
    with pytest.raises(TypeError):
        Outer.configure(**{"attr_h.attr_x": "value"})


def test_error_trying_to_configure_instance_variable():
    with pytest.raises(TypeError):
        Outer.configure(**{"attr_j.attr_a": "value"})
