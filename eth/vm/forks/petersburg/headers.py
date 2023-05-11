from eth.vm.forks.byzantium.headers import (
    compute_difficulty,
    configure_header,
    create_header_from_parent,
)

compute_petersburg_difficulty = compute_difficulty(5000000)

create_petersburg_header_from_parent = create_header_from_parent(
    compute_petersburg_difficulty
)
configure_petersburg_header = configure_header(
    difficulty_fn=compute_petersburg_difficulty
)
