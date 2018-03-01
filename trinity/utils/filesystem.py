import os


def is_same_path(p1: str, p2: str) -> bool:
    n_p1 = os.path.abspath(os.path.expanduser(p1))
    n_p2 = os.path.abspath(os.path.expanduser(p2))

    try:
        return os.path.samefile(n_p1, n_p2)
    except FileNotFoundError:
        return n_p1 == n_p2


def is_under_path(base_path: str, path: str, strict: bool=True) -> bool:
    if is_same_path(base_path, path):
        if strict:
            return False
        else:
            return True
    absolute_base_path = os.path.abspath(base_path)
    absolute_path = os.path.abspath(path)
    return absolute_path.startswith(absolute_base_path)
