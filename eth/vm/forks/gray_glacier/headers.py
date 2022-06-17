from eth.vm.forks.london.headers import (
    create_header_from_parent,
)
from eth.vm.forks.petersburg.headers import (
    compute_difficulty,
)
from eth.vm.forks.istanbul.headers import (
    configure_header,
)


compute_gray_glacier_difficulty = compute_difficulty(11_400_000)

create_gray_glacier_header_from_parent = create_header_from_parent(
    compute_gray_glacier_difficulty
)

configure_gray_glacier_header = configure_header(compute_gray_glacier_difficulty)
