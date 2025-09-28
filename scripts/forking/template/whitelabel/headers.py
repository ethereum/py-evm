from eth.vm.forks.petersburg.headers import (
    configure_header,
    create_header_from_parent,
    compute_petersburg_difficulty,
)


compute_istanbul_difficulty = compute_petersburg_difficulty

create_istanbul_header_from_parent = create_header_from_parent(
    compute_istanbul_difficulty
)
configure_istanbul_header = configure_header(compute_istanbul_difficulty)
