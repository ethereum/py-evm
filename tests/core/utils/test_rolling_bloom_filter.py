from trinity._utils.bloom import RollingBloom


def test_rolling_bloom_maintains_history():
    # only one historical filter
    bloom = RollingBloom(generation_size=10, max_generations=2)

    # fill up the main filter and the history
    for i in range(20):
        value = bytes((i,))
        bloom.add(value)
        assert value in bloom

    for i in range(20):
        value = bytes((i,))
        assert value in bloom

    # this should eject all of the 0-9 values
    bloom.add(b'\xff')

    # this must be done probabalistically since bloom filters have false
    # positives.  At least one of the 0-9 values should be gone.
    assert any(
        bytes((value,)) not in bloom
        for value in range(10)
    )

    for i in range(10, 20):
        value = bytes((i,))
        assert value in bloom
    assert b'\xff' in bloom
