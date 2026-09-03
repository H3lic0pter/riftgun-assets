"""Compress an image to under a target size, writing to a new file alongside the source.

Usage:
    python compress.py <filepath> [x]

The source image is never modified. Output is written to
<filepath-without-ext>_compressed.png. x is the size limit in MB (default 5).
Files already under the limit are reported and left untouched (no output file).

The downscale factor is found with a binary search so the result keeps the
largest resolution that still fits the limit, instead of stepping down blindly.
"""
import os
import sys

from PIL import Image

DEFAULT_LIMIT_MB = 5
MIN_SCALE = 0.1


def parse_limit(arg: str) -> float:
    try:
        value = float(arg)
    except ValueError:
        print("invalid size limit (MB):", arg)
        sys.exit(1)
    if value <= 0:
        print("size limit must be positive:", arg)
        sys.exit(1)
    return value


def output_path(path: str) -> str:
    root, ext = os.path.splitext(path)
    return root + "_compressed.png"


def save_candidate(base: Image.Image, out: str, scale: float) -> int:
    if scale >= 1.0:
        candidate = base
    else:
        size = (max(1, int(base.width * scale)), max(1, int(base.height * scale)))
        candidate = base.resize(size, Image.LANCZOS)
    candidate.save(out, "PNG", optimize=True, compress_level=9)
    return os.path.getsize(out)


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("usage: python compress.py <filepath> [x]")
        return 1
    path = sys.argv[1]
    limit_mb = parse_limit(sys.argv[2]) if len(sys.argv) == 3 else DEFAULT_LIMIT_MB
    limit_bytes = int(limit_mb * 1024 * 1024)

    if not os.path.exists(path):
        print("not found:", path)
        return 1
    original = os.path.getsize(path)
    if original <= limit_bytes:
        print("already under %g MB: %d bytes (no output written)" % (limit_mb, original))
        return 0

    img = Image.open(path)
    # RGBA screenshots with a fully opaque alpha channel save smaller as RGB.
    if img.mode in ("RGBA", "LA"):
        if img.getchannel("A").getextrema() == (255, 255):
            img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    out = output_path(path)
    # Full resolution first; if that fits, no downscale is needed.
    if save_candidate(img, out, 1.0) <= limit_bytes:
        new_size = os.path.getsize(out)
        print("compressed: %d -> %d bytes (%.2f MB)" % (original, new_size, new_size / 1048576.0))
        print("source kept:", path)
        print("output:", out)
        return 0

    # Binary search the largest scale in [MIN_SCALE, 1.0) that still fits.
    low, high = MIN_SCALE, 1.0
    best_size = -1
    for _ in range(16):
        mid = (low + high) / 2.0
        size = save_candidate(img, out, mid)
        if size <= limit_bytes:
            best_size = size
            low = mid  # try larger
        else:
            high = mid  # need smaller
    if best_size < 0:
        print("warning: still above %g MB even at %.0f%% scale" % (limit_mb, MIN_SCALE * 100))
        return 1

    # Ensure the chosen scale is actually on disk.
    final = save_candidate(img, out, low)
    if final > limit_bytes:
        print("warning: still above %g MB: %d bytes" % (limit_mb, final))
        return 1
    new_size = final
    print("compressed: %d -> %d bytes (%.2f MB)" % (original, new_size, new_size / 1048576.0))
    print("source kept:", path)
    print("output:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
