"""Huffman + ADPCM decompression used for some .wav files in MPQs.

Not implemented yet: added once real sound samples show which compression D2 uses.
"""
from .mpq import UnsupportedCompression


def decompress_huffman(data):
    raise UnsupportedCompression("huffman (sound) compression not implemented yet")


def decompress_adpcm(data, channels):
    raise UnsupportedCompression("ADPCM (sound) compression not implemented yet")
