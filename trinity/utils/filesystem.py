import os


def ensure_path_exists(dir_path):
    """
    Make sure that a path exists
    """
    os.makedirs(dir_path, exist_ok=True)
