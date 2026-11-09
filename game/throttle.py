"""Background level building must not make the game stutter: Python runs one thread at a time, so a
builder thread working flat out takes turns with the game's own thread and every animation hitches.
The game marks itself busy (animations playing, monsters' turn, a fight going on, the mouse being
used); builder threads call pause() at their natural break points and wait while it is busy."""
import threading
import time

_main = threading.main_thread()
_busy_until = 0.0


def busy(seconds=0.35):
    """The game is doing something the player watches: hold the builders for a moment."""
    global _busy_until
    t = time.time() + seconds
    if t > _busy_until:
        _busy_until = t


def pause():
    """Called by builder threads between pieces of work (a room stamped, a pack placed...)."""
    if threading.current_thread() is _main:
        return
    while time.time() < _busy_until:
        time.sleep(0.03)
    time.sleep(0)                   # and let the game's thread have the interpreter now and then


def release():
    """The game waits for a builder (a loading screen): let it run flat out."""
    global _busy_until
    _busy_until = 0.0
