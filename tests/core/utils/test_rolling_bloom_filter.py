from trinity._utils.bloom import RollingBloom


def test_rolling_bloom_maintains_history():
    # only one historical filter
    bloom = RollingBloom(generation_size=10, max_generations=2)

    bloom_values = tuple(bytes((i,)) for i in range(20))

    # fill up the main filter and the history
    for value in bloom_values:
        bloom.add(value)
        assert value in bloom

    # since the filter discards old history, we loop back over the values
    for value in bloom_values:
        assert value in bloom

    # this should eject all of the 0-9 values
    assert b'\xff' not in bloom_values
    bloom.add(b'\xff')

    # this must be done probabalistically since bloom filters have false
    # positives.  At least one of the 0-9 values should be gone.
    assert any(
        value not in bloom
        for value in bloom_values[:10]
    )

    for value in bloom_values[10:]:
        assert value in bloom
    assert b'\xff' in bloom
