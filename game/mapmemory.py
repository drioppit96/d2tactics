"""The automap you drew, kept in the save when "same maps every game" is on.

Each world's explored cells are stored as a compressed bit grid together with the map seed it was
drawn on; when that world is built again from the same seed, the map is filled back in.

    remember(player, key, world, seed)   - store this world's explored cells on the hero
    restore(player, key, world, seed)    - fill them back in (once per world)
"""
import base64
import zlib


def _encode(grid):
    w, h = grid.w, grid.h
    bits = bytearray((w * h + 7) // 8)
    cells = getattr(grid, "explored_cells", None)
    if cells is None:
        cells = [(x, y) for y in range(h) for x in range(w) if grid.explored[y][x]]
    for x, y in cells:
        i = y * w + x
        bits[i >> 3] |= 1 << (i & 7)
    return base64.b64encode(zlib.compress(bytes(bits), 9)).decode("ascii")


def remember(player, key, world, seed):
    if seed is None or world is None or getattr(world, "grid", None) is None:
        return
    g = world.grid
    cells = getattr(g, "explored_cells", None)
    n = len(cells) if cells is not None else -1
    if n == 0 or (n > 0 and getattr(world, "_map_saved_n", None) == n):
        return                      # nothing new since the last save
    store = getattr(player, "map_explored", None)
    if store is None:
        store = player.map_explored = {}
    store[str(key)] = dict(seed=seed, w=g.w, h=g.h, bits=_encode(g))
    world._map_saved_n = n


def restore(player, key, world, seed):
    if seed is None or world is None or getattr(world, "_map_restored", False):
        return False
    world._map_restored = True
    d = (getattr(player, "map_explored", None) or {}).get(str(key))
    g = world.grid
    if not d or d.get("seed") != seed or d.get("w") != g.w or d.get("h") != g.h:
        return False
    try:
        bits = zlib.decompress(base64.b64decode(d["bits"]))
    except Exception:
        return False
    w = g.w
    explored = g.explored
    cells = getattr(g, "explored_cells", None)
    new = getattr(g, "new_explored", None)
    for j, b in enumerate(bits):
        if not b:
            continue
        for k in range(8):
            if b & (1 << k):
                i = (j << 3) + k
                y, x = divmod(i, w)
                if y >= g.h:
                    break
                if not explored[y][x]:
                    explored[y][x] = True
                    if cells is not None:
                        cells.append((x, y))
                    if new is not None:
                        new.append((x, y))
    return True
