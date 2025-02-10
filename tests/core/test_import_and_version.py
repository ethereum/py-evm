def test_import_and_version():
    import eth

    assert isinstance(eth.__version__, str)
