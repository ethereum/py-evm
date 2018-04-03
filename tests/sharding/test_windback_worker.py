import logging

from tests.sharding.fixtures import (  # noqa: F401
    default_shard_id,
    mk_colhdr_chain,
    vmc,
    vmc_handler,
    windback_worker,
)


logger = logging.getLogger("evm.chain.sharding.windback_worker")
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(levelname)s] %(module)s::%(funcName)s\t| %(message)s")
console.setFormatter(formatter)
logger.addHandler(console)


def test_guess_head_no_new_collations(windback_worker, vmc):  # noqa: F811
    assert windback_worker.run_guess_head() is None


def test_guess_head_without_fork(windback_worker, vmc):  # noqa: F811
    header2_hash = mk_colhdr_chain(vmc, default_shard_id, 2)
    assert windback_worker.run_guess_head() == header2_hash
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 1, header2_hash)
    assert windback_worker.run_guess_head() == header3_hash
    # ensure all of the collations in the chain are verified
    assert len(windback_worker.collation_validity_cache) == 3


def test_guess_head_with_fork(windback_worker, vmc):  # noqa: F811
    # without fork
    mk_colhdr_chain(vmc, default_shard_id, 2)
    header3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    # head changes
    assert windback_worker.run_guess_head() == header3_prime_hash
    # ensure only the chain of the best candidate is verified
    assert len(windback_worker.collation_validity_cache) == 3


def test_guess_head_invalid_longest_chain(windback_worker, vmc):  # noqa: F811
    # setup two collation header chains, both having length=3.
    # originally, guess_head should return the hash of canonical chain head `header0_3_hash`
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    header4_hash = mk_colhdr_chain(vmc, default_shard_id, 1, top_collation_hash=header3_hash)
    header3_prime_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    windback_worker.collation_validity_cache[header3_hash] = False
    # the candidates is  [`header3`, `header3_prime`, `header2`, ...]
    # since the 1st candidate is invalid, `guess_head` should returns `header3_prime` instead
    assert windback_worker.run_guess_head() == header3_prime_hash
    assert not windback_worker.chain_validity[header4_hash]


def test_guess_head_new_only_candidate_is_invalid(windback_worker, vmc):  # noqa: F811
    head_header_hash = mk_colhdr_chain(vmc, default_shard_id, 1)
    windback_worker.collation_validity_cache[head_header_hash] = False
    windback_worker.chain_validity[head_header_hash] = False
    assert windback_worker.run_guess_head() is None


def test_guess_head_new_only_candidate_is_not_longest(windback_worker, vmc):  # noqa: F811
    head_header_hash = mk_colhdr_chain(vmc, default_shard_id, 3)
    windback_worker.run_guess_head()
    mk_colhdr_chain(vmc, default_shard_id, 1)
    assert windback_worker.run_guess_head() == head_header_hash


def test_guess_head_windback_length(windback_worker, vmc):  # noqa: F811
    # mock WINDBACK_LENGTH to a number less than the height of head_collation,
    # to make testing faster
    vmc.config['WINDBACK_LENGTH'] = 3
    # build a chain with head_collation_height = 5
    mk_colhdr_chain(vmc, default_shard_id, 5)
    windback_worker.run_guess_head()
    # the size of `collation_validity_cache` should be the WINDBACK_LENGTH + 1(including the
    # `head_collation` itself), instead of the length of the chain
    assert len(windback_worker.collation_validity_cache) == vmc.config['WINDBACK_LENGTH'] + 1


def test_guess_head_invalid_collation_propagate_invalidity(windback_worker, vmc):  # noqa: F811
    header2_hash = mk_colhdr_chain(vmc, default_shard_id, 2)
    windback_worker.collation_validity_cache[header2_hash] = False
    header4_hash = mk_colhdr_chain(vmc, default_shard_id, 2, header2_hash)
    windback_worker.run_guess_head()
    assert not windback_worker.chain_validity[header2_hash]
    assert not windback_worker.chain_validity[header4_hash]


def test_guess_head_invalid_chain_propagate_invalidity(windback_worker, vmc):  # noqa: F811
    header2_hash = mk_colhdr_chain(vmc, default_shard_id, 2)
    windback_worker.chain_validity[header2_hash] = False
    header3_hash = mk_colhdr_chain(vmc, default_shard_id, 1, header2_hash)
    header4_hash = mk_colhdr_chain(vmc, default_shard_id, 1, header3_hash)
    windback_worker.run_guess_head()
    assert not windback_worker.chain_validity[header3_hash]
    assert not windback_worker.chain_validity[header4_hash]
