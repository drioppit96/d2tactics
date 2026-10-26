"""D2 palettes: pal.dat is 256 BGR triplets."""


def load_palette(data):
    """Returns a list of 256 (r, g, b) tuples."""
    return [(data[i * 3 + 2], data[i * 3 + 1], data[i * 3]) for i in range(256)]
