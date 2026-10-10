

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
