import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

_SUBDIRS = (
    "core",
    os.path.join("core", "infra"),
    "parsers",
)


def install():
    added = []
    for sub in _SUBDIRS:
        path = os.path.normpath(os.path.join(_HERE, sub))
        if os.path.isdir(path) and path not in sys.path:
            sys.path.append(path)
            added.append(path)
    return added


def project_root():
    return _HERE


install()
