from termcolor import (
    colored,
)


def bold_green(txt: str) -> str:
    return colored(txt, "green", attrs=["bold"])


def bold_red(txt: str) -> str:
    return colored(txt, "red", attrs=["bold"])


def bold_yellow(txt: str) -> str:
    return colored(txt, "yellow", attrs=["bold"])


def bold_white(txt: str) -> str:
    return colored(txt, "white", attrs=["bold"])
