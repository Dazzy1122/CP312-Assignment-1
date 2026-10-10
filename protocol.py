"""
protocol.py - shared helpers for the text-based protocol.

Every command/response is ONE line of UTF-8 text ending in "\n":
    COMMAND: argument
Responses start with "OK: ..." or "ERROR: ...".
Raw file bytes are sent right after a line that announces their size.
"""

import hashlib
import os

CHUNK = 4096          # bytes per read/write during file transfer
MAX_LINE = 65536      # longest header line we accept
ENC = "utf-8"


def send_line(sock, text):
    """Send one text line."""
    sock.sendall((text + "\n").encode(ENC))


def read_line(rfile):
    """Read one line. Returns None if the peer disconnected, '' for an empty line."""
    data = rfile.readline(MAX_LINE)
    if not data:
        return None
    return data.decode(ENC, errors="replace").rstrip("\r\n")


def read_exact(rfile, n):
    """Yield chunks totalling exactly n bytes; raise ConnectionError if cut short."""
    remaining = n
    while remaining > 0:
        chunk = rfile.read(min(CHUNK, remaining))
        if not chunk:
            raise ConnectionError("Connection lost during file transfer")
        remaining -= len(chunk)
        yield chunk


def file_sha256(path):
    """SHA-256 hex digest of a file, read in chunks."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            sha.update(chunk)
    return sha.hexdigest()


def send_file(sock, path):
    """Send a file's raw bytes in chunks."""
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            sock.sendall(chunk)


def recv_file(rfile, path, size):
    """
    Receive exactly `size` bytes into `path` and return their SHA-256.
    Bytes go to `path + '.part'` first; the caller decides whether to keep it.
    The .part file is removed if the transfer is cut short.
    """
    part = path + ".part"
    sha = hashlib.sha256()
    try:
        with open(part, "wb") as f:
            for chunk in read_exact(rfile, size):
                f.write(chunk)
                sha.update(chunk)
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise
    return sha.hexdigest()


def parse_command(line):
    """'UPLOAD: a.txt' -> ('UPLOAD', 'a.txt'). Returns (None, None) if malformed."""
    if ":" in line:
        cmd, _, arg = line.partition(":")
    else:
        cmd, arg = line, ""
    cmd = cmd.strip().upper()
    if not cmd.isalpha():
        return None, None
    return cmd, arg.strip()
