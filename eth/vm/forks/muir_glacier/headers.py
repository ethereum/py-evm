from eth.vm.forks.istanbul.headers import (
    configure_header,
    create_header_from_parent,
)
from eth.vm.forks.petersburg.headers import (
    compute_difficulty,
)

compute_muir_glacier_difficulty = compute_difficulty(9000000)

create_muir_glacier_header_from_parent = create_header_from_parent(
    compute_muir_glacier_difficulty
)
configure_muir_glacier_header = configure_header(
    difficulty_fn=compute_muir_glacier_difficulty
)
