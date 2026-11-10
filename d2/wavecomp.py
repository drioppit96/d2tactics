"""Huffman + ADPCM decompression used for the .wav files in D2's MPQs (d2sfx, d2music, d2speech).

A Python port of StormLib's huff.cpp (adaptive Huffman, Faller-Gallager-Knuth) and adpcm.cpp
(Storm's IMA ADPCM variant) - StormLib is (c) Ladislav Zezula, MIT licensed.
Decoding is slowish in pure Python, so the game caches what it decodes (see render/sound.py).
"""

_WEIGHTS = [   # byte weights per data type (StormLib huff.cpp: sparse, binary, text, general, ADPCM 4/6, stereo 3/4/5)
    bytes.fromhex(
        "0a0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000002"),
    bytes.fromhex(
        "5416160d0c08060506050603040403050e0b141313090b0605040302030202020d070906060403020403030303030202"
        "090604040404030203020202020302040803040709050303030302020203020203020202020202020201010102010202"
        "060a0808060704030404020204020303040307070906040303020102020202020a020203020201010202020603050203"
        "0201010101010101010101020301010102010101010101020404040709080c0201010101010101010101010102010103"
        "040102040501010101010101020101010401010101010201010101010101010102010101010101010301010101010101"
        "0201010101010102020101020202064b"),
    bytes.fromhex(
        "0000000000000000000327000023000000000000000000000000000000000000ff0101010101010102020101060e1004"
        "060805040403030202030301010201010104020402020201010401010203030203010306040101010101010201020101"
        "0129071612400a0a112501031710262a100123232f100607020901010101010000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000"),
    bytes.fromhex(
        "ff0b07050b020202060202010402010309010101030401010201010102010101050101010d0101010101010101010101"
        "020101030101010101010102010101010a04020106030201010101010301010105020304030303020101010201020303"
        "01030101020501010403050103010303020104030a06010101010101010101010202010a020501010207021701050101"
        "0e0101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101"
        "060201040501010201010101020101010101010101010101010101010101010101010101010101010701010201010101"
        "02010101010101010201010101010111"),
    bytes.fromhex(
        "fffb989a848563643e3e2222131318170000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000"),
    bytes.fromhex(
        "fff19d9e9a9b9a9793938c8e868880827c7c7273696b5f6055564a4b404137372f2f272721211b1c1717131310100d0d"
        "0b0b09090808070706050504040419180000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000"),
    bytes.fromhex(
        "c3cbf541ff7bf72100000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000bfccf240fd7cf722000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000000000000000000000000000000000007a460000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000"),
    bytes.fromhex(
        "c3d9ef3df97ce91efdabf12cfc5bfe170000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000bdd9ec3df57de81dfbaef02cfb5cff1800000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000000000000000000000706c0000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000"),
    bytes.fromhex(
        "bac5da33e36dd818e594da23df4ad110eeafe42cea5ade15f487e921f643fc1200000000000000000000000000000000"
        "00000000000000000000000000000000b0c7d833e36bd618e795d823db49d011e9b2e22be85cdd15f187e720f744ff13"
        "00000000000000000000000000000000000000000000000000000000000000005f9e0000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000"),
]


def decompress_huffman(data, limit=1 << 26):
    """StormLib THuffmannTree::Decompress, without the quick-link cache (same output)."""
    n = len(data)
    if n == 0:
        return b""
    # nodes in parallel arrays; node 0 is the list head (sentinel)
    MAXN = 0x203 + 2
    nxt = [-1] * MAXN          # -1: not linked (NULL); 0: the list head
    prv = [-1] * MAXN
    nxt[0] = prv[0] = 0
    parent = [-1] * MAXN
    childlo = [-1] * MAXN
    weight = [0] * MAXN
    value = [0] * MAXN
    by_byte = [-1] * 0x102
    used = [1]

    def remove(i):
        if nxt[i] != -1:
            nx, pv = nxt[i], prv[i]
            nxt[pv] = nx
            prv[nx] = pv
            nxt[i] = prv[i] = -1

    def link_two(a, b):          # put b right after a
        nxt[b] = nxt[a]
        prv[b] = prv[nxt[a]]
        prv[nxt[a]] = b
        nxt[a] = b

    def find_higher_or_equal(i, w):
        if i >= 0:
            while i != 0:
                if weight[i] >= w:
                    return i
                i = prv[i]
        return 0

    def create(val, w, after):
        i = used[0]
        if i >= MAXN:
            return -1
        used[0] += 1
        remove(i)
        if after:
            link_two(0, i)
        else:
            link_two(prv[0], i)
        value[i] = val
        weight[i] = w
        parent[i] = -1
        childlo[i] = -1
        return i

    def fixup(i, maxw):
        if weight[i] < maxw:
            h = find_higher_or_equal(prv[0], weight[i])
            remove(i)
            link_two(h, i)
        else:
            maxw = weight[i]
        return maxw

    def inc_weights(i):
        while i >= 0:
            weight[i] += 1
            h = find_higher_or_equal(prv[i], weight[i])
            hi = nxt[h]
            if hi != i:
                remove(hi)
                link_two(i, hi)
                remove(i)
                link_two(h, i)
                lo = childlo[parent[hi]]
                par = parent[i]
                if childlo[par] == i:
                    childlo[par] = hi
                if lo == hi:
                    childlo[parent[hi]] = i
                par = parent[i]
                parent[i] = parent[hi]
                parent[hi] = par
            i = parent[i]

    def insert_branch(v1, v2):
        last = prv[0]
        hi = create(v1, weight[last], False)
        if hi < 0:
            return False
        parent[hi] = last
        by_byte[v1] = hi
        lo = create(v2, 0, False)
        if lo < 0:
            return False
        parent[lo] = last
        childlo[last] = lo
        by_byte[v2] = lo
        inc_weights(lo)
        return True

    pos = 0
    bitbuf = 0
    bitcnt = 0
    # the data type (8 bits)
    dtype = data[0]
    pos = 1
    sparse = dtype == 0
    if (dtype & 0x0F) >= len(_WEIGHTS):
        return b""
    table = _WEIGHTS[dtype & 0x0F]
    maxw = 0
    for b in range(256):
        if table[b]:
            i = create(b, table[b], True)
            by_byte[b] = i
            maxw = fixup(i, maxw)
    by_byte[0x100] = create(0x100, 1, False)
    by_byte[0x101] = create(0x101, 1, False)
    lo = prv[0]
    while lo != 0:
        hi = prv[lo]
        if hi == 0:
            break
        p = create(0, weight[hi] + weight[lo], True)
        if p < 0:
            return b""
        parent[lo] = p
        parent[hi] = p
        childlo[p] = lo
        maxw = fixup(p, maxw)
        lo = prv[hi]
    out = bytearray()
    while True:
        i = nxt[0]
        if i == 0:
            break
        while childlo[i] >= 0:
            if bitcnt == 0:
                if pos >= n:
                    return bytes(out)
                bitbuf = data[pos]
                pos += 1
                bitcnt = 8
            bit = bitbuf & 1
            bitbuf >>= 1
            bitcnt -= 1
            c = childlo[i]
            i = prv[c] if bit else c
        v = value[i]
        if v == 0x100:
            break
        if v == 0x101:
            if bitcnt < 8:
                if pos >= n:
                    break
                bitbuf |= data[pos] << bitcnt
                pos += 1
                bitcnt += 8
            v = bitbuf & 0xFF
            bitbuf >>= 8
            bitcnt -= 8
            if not insert_branch(value[prv[0]], v):
                break
            if not sparse:
                inc_weights(by_byte[v])
        if len(out) >= limit:
            break
        out.append(v)
        if sparse:
            inc_weights(by_byte[v])
    return bytes(out)


_NEXT_STEP = (-1, 0, -1, 4, -1, 2, -1, 6, -1, 1, -1, 5, -1, 3, -1, 7,
              -1, 1, -1, 5, -1, 3, -1, 7, -1, 2, -1, 4, -1, 6, -1, 8)
_STEP_SIZE = (7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66,
              73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449,
              494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272,
              2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493,
              10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767)


def decompress_adpcm(data, channels, limit=1 << 26):
    """StormLib DecompressADPCM: 16-bit PCM out."""
    import array
    n = len(data)
    if n < 2:
        return b""
    shift = data[1]
    pos = 2
    pred = [0, 0]
    step = [0x2C, 0x2C]
    out = array.array("h")
    for c in range(channels):
        if pos + 2 > n:
            return out.tobytes()
        s = data[pos] | (data[pos + 1] << 8)
        if s >= 0x8000:
            s -= 0x10000
        pos += 2
        pred[c] = s
        out.append(s)
    ch = channels - 1
    maxs = limit // 2
    while pos < n and len(out) < maxs:
        e = data[pos]
        pos += 1
        ch = (ch + 1) % channels
        if e == 0x80:
            if step[ch]:
                step[ch] -= 1
            out.append(pred[ch])
        elif e == 0x81:
            step[ch] += 8
            if step[ch] > 0x58:
                step[ch] = 0x58
            ch = (ch + 1) % channels
        else:
            si = step[ch]
            ss = _STEP_SIZE[si]
            d = ss >> shift
            if e & 0x01: d += ss
            if e & 0x02: d += ss >> 1
            if e & 0x04: d += ss >> 2
            if e & 0x08: d += ss >> 3
            if e & 0x10: d += ss >> 4
            if e & 0x20: d += ss >> 5
            p = pred[ch]
            if e & 0x40:
                p -= d
                if p <= -32768: p = -32768
            else:
                p += d
                if p >= 32767: p = 32767
            pred[ch] = p
            out.append(p)
            si += _NEXT_STEP[e & 0x1F]
            step[ch] = 0 if si < 0 else (88 if si > 88 else si)
    return out.tobytes()
