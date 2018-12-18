import resource


def get_open_fd_limit() -> int:
    """
    Return the OS soft limit of open file descriptors per process.
    """
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    return soft_limit
