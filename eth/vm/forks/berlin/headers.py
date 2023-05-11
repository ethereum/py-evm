from eth.vm.forks.muir_glacier.headers import (
    compute_muir_glacier_difficulty,
    configure_header,
    create_header_from_parent,
)

compute_berlin_difficulty = compute_muir_glacier_difficulty

create_berlin_header_from_parent = create_header_from_parent(compute_berlin_difficulty)
configure_berlin_header = configure_header(difficulty_fn=compute_berlin_difficulty)
