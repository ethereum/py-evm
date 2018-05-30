from trinity.utils.version import construct_trinity_client_identifier


def test_construct_trinity_client_identifier():
    assert construct_trinity_client_identifier().startswith('Trinity/')
