from evm.vm.forks.sharding.guess_head_state_manager import (
    fetch_and_verify_collation,
)

from tests.sharding.fixtures import (  # noqa: F401
    default_shard_id,
    mk_colhdr_chain,
    vmc,
    vmc_handler,
    ghs_manager,
)


def test_guess_head_state_manager_sync_without_fork(ghs_manager, vmc):  # noqa: F811
    # without fork
    header2_hash = mk_colhdr_chain(vmc, default_shard_id, 2)
    assert ghs_manager.guess_head_daemon(stop_after_create_collation=True) == header2_hash
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 1, header2_hash)
    assert ghs_manager.guess_head_daemon(stop_after_create_collation=True) == header3_hash


def test_guess_head_state_manager_sync_with_fork(ghs_manager, vmc):  # noqa: F811
    # without fork
    mk_colhdr_chain(vmc, default_shard_id, 2)
    header0_3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    # head changes
    assert ghs_manager.guess_head_daemon(stop_after_create_collation=True) == header0_3_prime_hash


def test_guess_head_state_manager_sync_invalid_chain(ghs_manager, vmc, monkeypatch):  # noqa: F811
    # setup two collation header chains, both having length=3.
    # originally, guess_head should return the hash of canonical chain head `header0_3_hash`
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    header3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)

    def mock_fetch_and_verify_collation(collation_hash):
        if collation_hash == header3_hash:
            return False
        return True
    # mock `fetch_and_verify_collation`, make it consider collation `header0_3_hash` is invalid
    fetch_and_verify_collation_import_path = "{0}.{1}".format(
        fetch_and_verify_collation.__module__,
        fetch_and_verify_collation.__name__,
    )
    monkeypatch.setattr(
        fetch_and_verify_collation_import_path,
        mock_fetch_and_verify_collation,
    )
    # the candidates is  [`header3`, `header3_prime`, `header2`, ...]
    # since the 1st candidate is invalid, `guess_head` should returns `header3_prime` instead
    assert ghs_manager.guess_head_daemon(stop_after_create_collation=True) == header3_prime_hash
