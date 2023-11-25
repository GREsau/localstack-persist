from collections.abc import Callable


def once(f: Callable[[], None]) -> Callable[[], None]:
    has_run = False

    def wrapper():
        nonlocal has_run
        if not has_run:
            has_run = True
            return f()

    return wrapper
