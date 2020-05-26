from eth.vm.forks.muir_glacier.headers import (
    configure_header,
    create_header_from_parent,
    compute_muir_glacier_difficulty,
)


compute_berlin_difficulty = compute_muir_glacier_difficulty

create_berlin_header_from_parent = create_header_from_parent(
    compute_berlin_difficulty
)
configure_berlin_header = configure_header(compute_berlin_difficulty)
