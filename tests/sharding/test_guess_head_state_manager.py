import asyncio

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


def test_guess_head_state_manager_daemon_async(ghs_manager, vmc):  # noqa: F811
    # without fork
    header_hash = mk_colhdr_chain(vmc, default_shard_id, 6)
    assert ghs_manager.async_daemon(stop_after_create_collation=True) == header_hash


def test_guess_head_state_manager_daemon_without_fork(ghs_manager, vmc):  # noqa: F811
    # without fork
    header2_hash = mk_colhdr_chain(vmc, default_shard_id, 2)
    assert ghs_manager.async_daemon(stop_after_create_collation=True) == header2_hash
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 1, header2_hash)
    assert ghs_manager.async_daemon(stop_after_create_collation=True) == header3_hash


def test_guess_head_state_manager_daemon_with_fork(ghs_manager, vmc):  # noqa: F811
    # without fork
    mk_colhdr_chain(vmc, default_shard_id, 2)
    header0_3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    # head changes
    assert ghs_manager.async_daemon(stop_after_create_collation=True) == header0_3_prime_hash


def test_guess_head_state_manager_daemon_invalid_chain(ghs_manager, vmc):  # noqa: F811
    # setup two collation header chains, both having length=3.
    # originally, guess_head should return the hash of canonical chain head `header0_3_hash`
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    header3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    ghs_manager.collation_validity_cache[header3_hash] = False
    ghs_manager.head_validity[header3_hash] = False
    # the candidates is  [`header3`, `header3_prime`, `header2`, ...]
    # since the 1st candidate is invalid, `guess_head` should returns `header3_prime` instead
    assert ghs_manager.async_daemon(stop_after_create_collation=True) == header3_prime_hash


def wait_for_tasks_complete(ghs_manager):
    '''
    Used to complete the unfinished verification works
    '''
    event_loop = asyncio.get_event_loop()
    for task in ghs_manager.tasks:
        event_loop.run_until_complete(task)


def test_guess_head_state_manager_step_by_step(ghs_manager, vmc):  # noqa: F811
    # assume collations "A B C D E F" are added
    head_collation_hash = mk_colhdr_chain(
        vmc,
        default_shard_id,
        6,
    )
    current_collation_hash = head_collation_hash

    # assume ghs_manager just found itself to be a collator in the lookahead periods,
    # so it keep doing `guess_head`

    # fetch one candidate and set it as the head
    ghs_manager.try_change_head()
    assert ghs_manager.head_collation_hash == head_collation_hash
    assert ghs_manager.current_collation_hash == current_collation_hash
    # process one collation of the current chain
    ghs_manager.process_current_collation()
    wait_for_tasks_complete(ghs_manager)
    assert (
        (current_collation_hash in ghs_manager.collation_validity_cache) and
        ghs_manager.collation_validity_cache[current_collation_hash]
    )

    ghs_manager.try_change_head()
    # `head_collation_hash` should remain the same since the chain is still valid
    assert ghs_manager.head_collation_hash == head_collation_hash
    current_collation_hash = vmc.get_parent_hash(default_shard_id, current_collation_hash)
    assert ghs_manager.current_collation_hash == current_collation_hash
    assert ghs_manager.head_collation_hash != ghs_manager.current_collation_hash
    # if current_collation is verified
    ghs_manager.process_current_collation()
    wait_for_tasks_complete(ghs_manager)
    assert (
        (current_collation_hash in ghs_manager.collation_validity_cache) and
        ghs_manager.collation_validity_cache[current_collation_hash]
    )

    # one period elapses and a new collation created
    new_head_hash = mk_colhdr_chain(
        vmc,
        default_shard_id,
        3,
        top_collation_hash=head_collation_hash,
    )
    # since new collation head is added, head should be changed
    ghs_manager.try_change_head()
    assert ghs_manager.head_collation_hash == new_head_hash
    # and because head collation changed, we start verifying the chain from the head
    assert ghs_manager.current_collation_hash == new_head_hash
    ghs_manager.process_current_collation()
    wait_for_tasks_complete(ghs_manager)

    # although we don't have enough time to verify all collation in this chain, we still guess that
    # the chain head is `head_collation`
    ghs_manager.try_change_head()
    ghs_manager.process_current_collation()
    wait_for_tasks_complete(ghs_manager)
    assert ghs_manager.try_create_collation() == new_head_hash
