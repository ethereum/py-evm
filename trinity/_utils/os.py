import re
import resource
import unicodedata


def get_open_fd_limit() -> int:
    """
    Return the OS soft limit of open file descriptors per process.
    """
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    return soft_limit


def friendly_filename_or_url(value: str) -> str:
    """
    Normalize any string to be file name and URL friendly.
    Convert to lowercase, remove non-alpha characters,
    and convert spaces to hyphens.
    """
    # Taken from:
    # https://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename/295466#295466
    value = str(unicodedata.normalize('NFKD', value).encode('ascii', 'ignore'))
    value = str(re.sub('[^\w\s-]', '', value).strip().lower())
    value = str(re.sub('[-\s]+', '-', value))
    return value
