"""Locked, atomic portfolio writes for the web layer. Stdlib-only.

Core ledger.py stays untouched: Portfolio.save() writes wherever `path` points,
so we save to a temp file in the same directory and os.replace() it over the
real one (atomic on POSIX). The flock serializes all webapp writers
(double-submits, two tabs); a simultaneous CLI `record` is the same exposure
as two concurrent CLI runs today — the cron daily job only reads.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ...portfolio import Portfolio

try:
    import fcntl
except ImportError:  # pragma: no cover — non-POSIX fallback: no inter-process lock
    fcntl = None


@contextmanager
def locked_portfolio(path: Path) -> Iterator[Portfolio]:
    """Load-modify-save under an exclusive lock; atomic replace on exit.

    The caller mutates the yielded Portfolio via Position.record_* methods,
    which raise ValueError BEFORE any state is written — an exception inside
    the block leaves the file untouched.
    """
    lock_path = path.with_name(path.name + ".lock")
    with open(lock_path, "w") as lf:
        if fcntl is not None:
            fcntl.flock(lf, fcntl.LOCK_EX)
        pf = Portfolio.load(path)
        yield pf
        tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
        pf.path = tmp
        try:
            pf.save()
            os.replace(tmp, path)
        finally:
            pf.path = path
            if tmp.exists():  # save or replace failed — don't leave orphans
                tmp.unlink()
