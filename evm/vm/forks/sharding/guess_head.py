validity_cache = {}


def fake_fetch_and_verify_collation(collation_hash):
    # I don't do anything
    return True


fetch_and_verify_collation = fake_fetch_and_verify_collation


def memoized_fetch_and_verify_collation(collation_hash):
    if collation_hash not in validity_cache:
        validity_cache[collation_hash] = fetch_and_verify_collation(collation_hash)
    return validity_cache[collation_hash]


def guess_head(vmc_handler, shard_id):
    head_collation_hash = None
    while True:
        head_collation_hash = vmc_handler.fetch_candidate_head(shard_id)
        current_collation_hash = head_collation_hash
        while True:
            if not memoized_fetch_and_verify_collation(current_collation_hash):
                break
            current_collation_hash = vmc_handler.get_parent_hash(current_collation_hash)
