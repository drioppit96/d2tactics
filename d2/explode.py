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


def _fast_table(h, nsym):
    """Lookup table: 13 peeked bits (LSB first, as read) -> (symbol, code length)."""
    table = [None] * (1 << MAXBITS)
    code = 0
    idx = 0
    for ln in range(1, MAXBITS + 1):
        for _ in range(h.count[ln]):
            sym = h.symbol[idx]
            idx += 1
            # bits as they appear in the stream: MSB of the code first, each bit inverted
            p = 0
            for k in range(ln):
                p |= (((code >> (ln - 1 - k)) & 1) ^ 1) << k
            step = 1 << ln
            for fill in range(p, 1 << MAXBITS, step):
                table[fill] = (sym, ln)
            code += 1
        code <<= 1
    return table


_FAST_LIT = _fast_table(_LITCODE, 256)
_FAST_LEN = _fast_table(_LENCODE, 16)
_FAST_DIST = _fast_table(_DISTCODE, 64)


def explode(data, expected_size=None):
    """Table-driven decoder (several times faster than the bit-by-bit reference below)."""
    src = data
    n = len(src)
    if n < 2:
        raise ExplodeError("too short")
    lit = src[0]
    dict_bits = src[1]
    if lit > 1:
        raise ExplodeError("bad literal flag")
    if dict_bits < 4 or dict_bits > 6:
        raise ExplodeError("bad dictionary size")
    pos = 2
    bitbuf = 0
    bitcnt = 0
    out = bytearray()
    want = expected_size if expected_size is not None else -1
    T_LIT, T_LEN, T_DIST = _FAST_LIT, _FAST_LEN, _FAST_DIST
    BASE, EXTRA = _BASE, _EXTRA
    MASK13 = (1 << MAXBITS) - 1
    while True:
        # keep at least 32 bits in the buffer (pad with zeros past the end)
        while bitcnt < 32:
            bitbuf |= (src[pos] if pos < n else 0) << bitcnt
            pos += 1
            bitcnt += 8
        if bitbuf & 1:
            bitbuf >>= 1
            bitcnt -= 1
            sym, ln = T_LEN[bitbuf & MASK13]
            bitbuf >>= ln
            bitcnt -= ln
            e = EXTRA[sym]
            length = BASE[sym] + (bitbuf & ((1 << e) - 1))
            bitbuf >>= e
            bitcnt -= e
            if length == 519:
                break
            while bitcnt < 32:
                bitbuf |= (src[pos] if pos < n else 0) << bitcnt
                pos += 1
                bitcnt += 8
            sb = 2 if length == 2 else dict_bits
            dsym, ln = T_DIST[bitbuf & MASK13]
            bitbuf >>= ln
            bitcnt -= ln
            dist = (dsym << sb) + (bitbuf & ((1 << sb) - 1)) + 1
            bitbuf >>= sb
            bitcnt -= sb
            olen = len(out)
            if dist > olen:
                raise ExplodeError("distance too far back")
            start = olen - dist
            if dist >= length:
                out += out[start:start + length]
            else:
                chunk = bytes(out[start:olen])
                out += (chunk * (length // dist + 1))[:length]
        else:
            bitbuf >>= 1
            bitcnt -= 1
            if lit:
                sym, ln = T_LIT[bitbuf & MASK13]
                bitbuf >>= ln
                bitcnt -= ln
                out.append(sym)
            else:
                out.append(bitbuf & 0xFF)
                bitbuf >>= 8
                bitcnt -= 8
        if want >= 0 and len(out) >= want:
            break
        if pos > n + 8:
            raise ExplodeError("ran out of input")
    return bytes(out)


def explode_reference(data, expected_size=None):
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
