"""
server.py - TCP server for messaging and file transfer.

Usage: python3 server.py [host] [port]      (defaults 127.0.0.1 5000)

Serves one client at a time. When a client leaves, waits for the next one.
Stop with Ctrl+C.
"""

import json
import os
import socket
import sys
import time

from protocol import file_sha256, parse_command, read_line, recv_file, send_file, send_line

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.txt")
STORAGE = os.path.join(BASE_DIR, "server_files")


def log(tag, text):
    print(f"[{time.strftime('%H:%M:%S')}] [{tag}] {text}")


def load_users():
    with open(USERS_FILE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def list_files():
    """Sorted [name, size] pairs for every finished file in storage."""
    files = []
    for name in sorted(os.listdir(STORAGE)):
        path = os.path.join(STORAGE, name)
        if os.path.isfile(path) and not name.endswith(".part"):
            files.append([name, os.path.getsize(path)])
    return files


def do_upload(conn, rfile, arg):
    try:
        name, size, digest = arg.rsplit("|", 2)
        name = os.path.basename(name)
        size = int(size)
        if name in ("", ".", "..") or size < 0:
            raise ValueError
    except ValueError:
        send_line(conn, "ERROR: Bad UPLOAD format. Use UPLOAD: name|size|sha256")
        return
    path = os.path.join(STORAGE, name)
    send_line(conn, "OK: READY")
    received = recv_file(rfile, path, size)
    if received != digest:
        os.remove(path + ".part")
        log("ERROR", f"Checksum mismatch for '{name}', discarded")
        send_line(conn, "ERROR: Checksum mismatch, file discarded")
    else:
        os.replace(path + ".part", path)
        log("FILE RECEIVED", f"'{name}' ({size} bytes)")
        send_line(conn, f"OK: File '{name}' uploaded ({size} bytes)")


def do_download(conn, arg):
    name = os.path.basename(arg)
    path = os.path.join(STORAGE, name)
    if name in ("", ".", "..") or name.endswith(".part") or not os.path.isfile(path):
        log("ERROR", f"File not found: '{name}'")
        send_line(conn, f"ERROR: File '{name}' not found")
        return
    size = os.path.getsize(path)
    send_line(conn, f"OK: {size}|{file_sha256(path)}")
    send_file(conn, path)
    log("FILE SENT", f"'{name}' ({size} bytes)")


def handle_client(conn, rfile, users):
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
            if not arg:
                send_line(conn, "ERROR: Missing username")
            elif arg in users:
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
                send_line(conn, "OK: " + json.dumps(list_files()))
            elif cmd == "UPLOAD":
                do_upload(conn, rfile, arg)
            elif cmd == "DOWNLOAD":
                do_download(conn, arg)
        else:
            log("ERROR", f"Invalid command: {cmd}")
            send_line(conn, f"ERROR: Invalid command '{cmd}'")


def main():
    try:
        host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    except ValueError:
        print("Usage: python3 server.py [host] [port]")
        return
    try:
        users = load_users()
    except FileNotFoundError:
        print(f"Missing {USERS_FILE}. Create it with one username per line.")
        return
    os.makedirs(STORAGE, exist_ok=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
    except OSError as e:
        print(f"Could not start server on {host}:{port}: {e}")
        server.close()
        return
    server.listen(1)
    log("SERVER", f"Listening on {host}:{port} (Ctrl+C to stop)")
    try:
        while True:
            conn, addr = server.accept()
            log("CLIENT CONNECTED", f"{addr[0]}:{addr[1]}")
            rfile = conn.makefile("rb")
            try:
                handle_client(conn, rfile, users)
            except OSError as e:  # includes ConnectionError and disk errors
                log("ERROR", f"Connection problem: {e}")
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
