
import hashlib
import json
import os
import socket
import sys
import time

from protocol import CHUNK, parse_command, read_exact, read_line, send_line

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
USERS_FILE = "users.txt"
STORAGE = "server_storage"


def log(tag, text):
    print(f"[{time.strftime('%H:%M:%S')}] [{tag}] {text}")


def load_users():
    with open(USERS_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def do_upload(conn, rfile, arg):
    try:
        name, size, digest = arg.split("|")
        name = os.path.basename(name)
        size = int(size)
        if not name or size < 0:
            raise ValueError
    except ValueError:
        send_line(conn, "ERROR: Bad UPLOAD format. Use UPLOAD: name|size|sha256")
        return
    os.makedirs(STORAGE, exist_ok=True)
    path = os.path.join(STORAGE, name)
    send_line(conn, "OK: READY")
    sha = hashlib.sha256()
    with open(path, "wb") as f:
        for chunk in read_exact(rfile, size):
            f.write(chunk)
            sha.update(chunk)
    if sha.hexdigest() != digest:
        os.remove(path)
        log("ERROR", f"Checksum mismatch for '{name}', discarded")
        send_line(conn, "ERROR: Checksum mismatch, file discarded")
    else:
        log("FILE RECEIVED", f"'{name}' ({size} bytes) -> {path}")
        send_line(conn, f"OK: File '{name}' uploaded ({size} bytes)")


def do_download(conn, arg):
    name = os.path.basename(arg)
    path = os.path.join(STORAGE, name)
    if not name or not os.path.isfile(path):
        send_line(conn, f"ERROR: File '{name}' not found")
        return
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            sha.update(chunk)
    size = os.path.getsize(path)
    send_line(conn, f"OK: {size}|{sha.hexdigest()}")
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            conn.sendall(chunk)
    log("FILE SENT", f"'{name}' ({size} bytes)")


def handle_client(conn, rfile):
    user = None
    while True:
        line = read_line(rfile)
        if line is None:
            log("INFO", "Client closed the connection unexpectedly")
            return
        if line.strip() == "":
            send_line(conn, "ERROR: Empty message")
            continue

        cmd, arg = parse_command(line)
        if cmd is None:
            log("ERROR", f"Malformed line: {line!r}")
            send_line(conn, "ERROR: Incorrect protocol format. Use COMMAND: argument")
        elif cmd == "QUIT":
            send_line(conn, "OK: Goodbye")
            return
        elif cmd == "LOGIN":
            if arg in load_users():
                user = arg
                log("LOGIN", f"User '{user}' logged in")
                send_line(conn, f"OK: Welcome {user}")
            else:
                log("ERROR", f"Login failed for '{arg}'")
                send_line(conn, "ERROR: Unknown user")
        elif cmd in ("MSG", "LIST", "UPLOAD", "DOWNLOAD"):
            if user is None:
                send_line(conn, "ERROR: Please LOGIN first")
            elif cmd == "MSG":
                if not arg:
                    send_line(conn, "ERROR: Empty message")
                else:
                    log("MESSAGE RECEIVED", f"{user}: {arg}")
                    send_line(conn, "OK: Message received")
            elif cmd == "LIST":
                files = sorted(os.listdir(STORAGE)) if os.path.isdir(STORAGE) else []
                send_line(conn, "OK: " + json.dumps(files))
            elif cmd == "UPLOAD":
                do_upload(conn, rfile, arg)
            elif cmd == "DOWNLOAD":
                do_download(conn, arg)
        else:
            log("ERROR", f"Invalid command: {cmd}")
            send_line(conn, f"ERROR: Invalid command '{cmd}'")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    log("SERVER", f"Listening on {HOST}:{PORT} (Ctrl+C to stop)")
    try:
        while True:
            conn, addr = server.accept()
            log("CLIENT CONNECTED", f"{addr[0]}:{addr[1]}")
            rfile = conn.makefile("rb")
            try:
                handle_client(conn, rfile)
            except (ConnectionError, OSError) as e:
                log("ERROR", f"Connection problem: {e}")
            except FileNotFoundError as e:
                log("ERROR", f"Missing file: {e}")
            finally:
                rfile.close()
                conn.close()
                log("CLIENT DISCONNECTED", f"{addr[0]}:{addr[1]}")
    except KeyboardInterrupt:
        print()
        log("SERVER", "Shutting down")
    finally:
        server.close()


if __name__ == "__main__":
    main()
