from eth.vm.forks.byzantium.headers import (
    configure_header,
    create_header_from_parent,
    compute_difficulty,
)


compute_petersburg_difficulty = compute_difficulty(5000000)

create_petersburg_header_from_parent = create_header_from_parent(
    compute_petersburg_difficulty
)
configure_petersburg_header = configure_header(compute_petersburg_difficulty)
