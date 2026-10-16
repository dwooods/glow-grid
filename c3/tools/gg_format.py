"""Reading and writing Glow Grid sprite files (.gg), version 1. See ../gg_core.h for the layout."""
import struct

COLS = ROWS = 16
HEADER_SIZE = 12
FRAME_BYTES = COLS * ROWS * 3
MAX_FRAMES = 16


def pack(frames, fps, brightness, gamma):
    """frames: list of 256-entry lists of (r, g, b), row by row from the top-left, uncorrected.
    Returns the file bytes."""
    if not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"need 1 to {MAX_FRAMES} frames, got {len(frames)}")
    fps10 = round(float(fps) * 10)
    bright = round(float(brightness) * 100)
    gamma10 = round(float(gamma) * 10)
    if not 5 <= fps10 <= 300:
        raise ValueError(f"fps {fps} out of range (0.5 to 30)")
    if not 1 <= bright <= 100:
        raise ValueError(f"brightness {brightness} out of range (0.01 to 1.0)")
    if not 10 <= gamma10 <= 30:
        raise ValueError(f"gamma {gamma} out of range (1.0 to 3.0)")
    out = bytearray(b"GG")
    out += struct.pack("<BBBBHHBB", 1, 0, COLS, ROWS, len(frames), fps10, bright, gamma10)
    for fr in frames:
        if len(fr) != COLS * ROWS:
            raise ValueError("each frame needs 256 pixels")
        for r, g, b in fr:
            out += bytes((r, g, b))
    return bytes(out)


def unpack(blob):
    """Returns (frames, fps, brightness, gamma). Raises ValueError for anything invalid."""
    if len(blob) < HEADER_SIZE:
        raise ValueError("too short")
    if blob[:2] != b"GG":
        raise ValueError("bad magic")
    version, flags, cols, rows, frames, fps10, bright, gamma10 = struct.unpack("<BBBBHHBB", blob[2:HEADER_SIZE])
    if version != 1:
        raise ValueError("unknown version")
    if (cols, rows) != (COLS, ROWS):
        raise ValueError("wrong grid size")
    if not 1 <= frames <= MAX_FRAMES:
        raise ValueError("bad frame count")
    if len(blob) != HEADER_SIZE + frames * FRAME_BYTES:
        raise ValueError("size does not match frames")
    out = []
    pos = HEADER_SIZE
    for _ in range(frames):
        fr = [tuple(blob[pos + 3 * i: pos + 3 * i + 3]) for i in range(COLS * ROWS)]
        out.append(fr)
        pos += FRAME_BYTES
    return out, fps10 / 10.0, bright / 100.0, gamma10 / 10.0
