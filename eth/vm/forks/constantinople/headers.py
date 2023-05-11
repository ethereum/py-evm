from eth.vm.forks.byzantium.headers import (
    compute_difficulty,
    configure_header,
    create_header_from_parent,
)

compute_constantinople_difficulty = compute_difficulty(5000000)

create_constantinople_header_from_parent = create_header_from_parent(
    compute_constantinople_difficulty
)
configure_constantinople_header = configure_header(
    difficulty_fn=compute_constantinople_difficulty
)
