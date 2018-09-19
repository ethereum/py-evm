from eth.vm.forks.byzantium.headers import (
    configure_header,
    create_header_from_parent,
    compute_difficulty,
)


compute_constantinople_difficulty = compute_difficulty(5000000)

create_constantinople_header_from_parent = create_header_from_parent(
    compute_constantinople_difficulty
)
configure_constantinople_header = configure_header(compute_constantinople_difficulty)
