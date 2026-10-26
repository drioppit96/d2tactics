"""PKWARE Data Compression Library "explode" (the decompressor D2's MPQs use).

A port of Mark Adler's public-domain blast.c.
"""

MAXBITS = 13

# compact code-length tables from blast.c: low nibble = code length, high nibble + 1 = repeat count
_LITLEN = [
    11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8,
    9, 7, 6, 7, 8, 7, 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5,
    7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7, 9, 8, 25, 11, 8, 11, 9, 12,
    8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24, 10, 27,
    44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
    44, 173]
_LENLEN = [2, 35, 36, 53, 38, 23]
_DISTLEN = [2, 20, 53, 230, 247, 151, 248]
_BASE = [3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264]
_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8]


class _Huffman:
    def __init__(self, rep, n_symbols):
        lengths = []
        for b in rep:
            lengths += [b & 15] * ((b >> 4) + 1)
        if len(lengths) != n_symbols:
            raise ValueError("bad code table (%d != %d)" % (len(lengths), n_symbols))
        self.count = [0] * (MAXBITS + 1)
        for ln in lengths:
            self.count[ln] += 1
        offs = [0] * (MAXBITS + 2)
        for ln in range(1, MAXBITS):
            offs[ln + 1] = offs[ln] + self.count[ln]
        self.symbol = [0] * n_symbols
        for sym, ln in enumerate(lengths):
            if ln:
                self.symbol[offs[ln]] = sym
                offs[ln] += 1


_LITCODE = _Huffman(_LITLEN, 256)
_LENCODE = _Huffman(_LENLEN, 16)
_DISTCODE = _Huffman(_DISTLEN, 64)


class ExplodeError(Exception):
    pass


def explode(data, expected_size=None):
    src = data
    n = len(src)
    pos = 0
    bitbuf = 0
    bitcnt = 0
    out = bytearray()

    def need(k):
        nonlocal pos, bitbuf, bitcnt
        while bitcnt < k:
            if pos >= n:
                raise ExplodeError("ran out of input")
            bitbuf |= src[pos] << bitcnt
            pos += 1
            bitcnt += 8

    def bits(k):
        nonlocal bitbuf, bitcnt
        if k == 0:
            return 0
        need(k)
        v = bitbuf & ((1 << k) - 1)
        bitbuf >>= k
        bitcnt -= k
        return v

    def decode(h):
        nonlocal bitbuf, bitcnt
        code = first = index = 0
        count = h.count
        for ln in range(1, MAXBITS + 1):
            need(1)
            code |= (bitbuf & 1) ^ 1       # codes are stored inverted
            bitbuf >>= 1
            bitcnt -= 1
            c = count[ln]
            if code - first < c:
                return h.symbol[index + code - first]
            index += c
            first = (first + c) << 1
            code <<= 1
        raise ExplodeError("bad code")

    lit = bits(8)
    if lit > 1:
        raise ExplodeError("bad literal flag")
    dict_bits = bits(8)
    if dict_bits < 4 or dict_bits > 6:
        raise ExplodeError("bad dictionary size")
    while True:
        if bits(1):
            sym = decode(_LENCODE)
            length = _BASE[sym] + bits(_EXTRA[sym])
            if length == 519:
                break   # end of stream
            sb = 2 if length == 2 else dict_bits
            dist = (decode(_DISTCODE) << sb) + bits(sb) + 1
            if dist > len(out):
                raise ExplodeError("distance too far back")
            start = len(out) - dist
            if dist >= length:
                out += out[start:start + length]
            else:
                for i in range(length):
                    out.append(out[start + i])
        else:
            out.append(decode(_LITCODE) if lit else bits(8))
        if expected_size is not None and len(out) >= expected_size:
            break
    return bytes(out)
