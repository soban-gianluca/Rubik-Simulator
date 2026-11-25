"""Runs the Kociemba solver in a separate process.

The search is pure Python: in a thread it holds the interpreter lock, and every frame
waited behind it (frames went from 10 ms to almost 2 s while a hint was computed).
In its own process it runs in parallel and the threads that ask for a solve only wait.
"""
import os
import threading
from concurrent.futures import ProcessPoolExecutor

SOLVED = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"

_pool = None


def _exit_with_parent():
    """Worker side: quit when the game process ends, even if it crashed or was killed."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x00100000, False, os.getppid())  # SYNCHRONIZE
    if handle:
        def watch():
            kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)  # INFINITE
            os._exit(0)
        threading.Thread(target=watch, daemon=True).start()


def _solve(facelets, max_depth=22, timeout=5):
    from src.pykociemba.search import Search
    # 22, not 21: some scrambles need over 5 s to find a 21 move solution, and the hint then failed
    return Search().solution(facelets, maxDepth=max_depth, timeOut=timeout, useSeparator=False)


def start():
    """Start the worker and load the solver tables there before the first hint is needed."""
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=1, initializer=_exit_with_parent)
        _pool.submit(_solve, SOLVED)
    return _pool


def solve(facelets, max_depth=22, timeout=5):
    """Solution string for a facelet string (blocks the calling thread, not the game)."""
    return start().submit(_solve, facelets, max_depth, timeout).result(timeout=30)


def shutdown():
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
