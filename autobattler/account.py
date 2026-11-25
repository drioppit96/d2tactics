"""Account-wide currencies of the D2 Autobattler (saves_auto/_account.json), shared by every hero.

    rare_cores   one for every rare (yellow) item any hero sells; spent in the Horadric Cube
"""
import json
import os

CURRENCIES = {"rare_cores": "Rare Cores"}
_DATA = [None]


def _path():
    from game import save as gsave
    return os.path.join(gsave.NORMAL_DIR, "_account.json")


def data():
    d = _DATA[0]
    if d is None:
        d = {}
        try:
            with open(_path()) as f:
                d = json.load(f) or {}
        except (OSError, ValueError):
            d = {}
        for k in CURRENCIES:
            d[k] = int(d.get(k, 0) or 0)
        _DATA[0] = d
    return d


def save():
    try:
        with open(_path(), "w") as f:
            json.dump(data(), f)
    except OSError:
        pass


def amount(key):
    return int(data().get(key, 0) or 0)


def add(key, n=1):
    data()[key] = amount(key) + int(n)
    save()
    return amount(key)


def can_pay(cost):
    return all(amount(k) >= int(v) for k, v in (cost or {}).items())


def pay(cost):
    """Takes the cost if there is enough of everything. -> True if paid."""
    if not can_pay(cost):
        return False
    for k, v in (cost or {}).items():
        data()[k] = amount(k) - int(v)
    save()
    return True


def reset_cache():
    _DATA[0] = None
