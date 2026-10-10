"""
client.py - interactive TCP client for messaging and file transfer.

Usage: python3 client.py [host] [port]      (defaults 127.0.0.1 5000)

Type HELP at the prompt for the list of commands.
"""

import json
import os
import socket
import sys

from protocol import file_sha256, read_line, recv_file, send_file, send_line

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(BASE_DIR, "client_files")
DOWNLOADS_DIR = os.path.join(FILES_DIR, "downloads")

HELP_TEXT = """Commands:
  LOGIN <username>     log in as a user listed on the server
  MSG <text>           send a text message
  LIST                 list files on the server
  UPLOAD <filename>    send client_files/<filename> to the server
  DOWNLOAD <filename>  save a server file into client_files/downloads/
  HELP                 show this list
  QUIT                 disconnect and exit"""


def get_reply(rfile):
    """Read one server reply line; raise ConnectionError if the server is gone."""
    reply = read_line(rfile)
    if reply is None:
        raise ConnectionError("Server closed the connection")
    return reply


def do_upload(sock, rfile, name):
    path = os.path.join(FILES_DIR, name)
    if not os.path.isfile(path):
        print(f"[client] File '{name}' not found in client_files/")
        return
    size = os.path.getsize(path)
    send_line(sock, f"UPLOAD: {name}|{size}|{file_sha256(path)}")
    reply = get_reply(rfile)
    if not reply.startswith("OK"):
        print(reply)  # e.g. not logged in; don't send the bytes
        return
    print(f"Uploading '{name}' ({size} bytes)...")
    send_file(sock, path)
    print(get_reply(rfile))


def do_download(sock, rfile, name):
    send_line(sock, f"DOWNLOAD: {name}")
    reply = get_reply(rfile)
    if not reply.startswith("OK"):
        print(reply)
        return
    size, digest = reply[len("OK:"):].strip().split("|")
    size = int(size)
    path = os.path.join(DOWNLOADS_DIR, os.path.basename(name))
    print(f"Downloading '{name}' ({size} bytes)...")
    if recv_file(rfile, path, size) == digest:
        os.replace(path + ".part", path)
        print(f"OK: Downloaded '{name}' ({size} bytes), checksum verified -> {path}")
    else:
        os.remove(path + ".part")
        print("ERROR: Checksum mismatch, download discarded")


def do_list(sock, rfile):
    send_line(sock, "LIST")
    reply = get_reply(rfile)
    if not reply.startswith("OK"):
        print(reply)
        return
    files = json.loads(reply[len("OK:"):])
    if not files:
        print("No files on the server.")
    for name, size in files:
        print(f"  {name:<40} {size} bytes")


def run(sock, rfile):
    """Prompt loop. Returns when the user quits."""
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            line = "QUIT"
        if not line:
            continue
        cmd, _, arg = line.partition(" ")
        cmd, arg = cmd.upper(), arg.strip()

        if cmd == "HELP":
            print(HELP_TEXT)
        elif cmd == "QUIT":
            send_line(sock, "QUIT")
            print(get_reply(rfile))
            return
        elif cmd == "LIST":
            do_list(sock, rfile)
        elif cmd in ("LOGIN", "MSG", "UPLOAD", "DOWNLOAD") and not arg:
            print(f"[client] Usage: {cmd} <{'text' if cmd == 'MSG' else 'name'}>")
        elif cmd == "UPLOAD":
            do_upload(sock, rfile, arg)
        elif cmd == "DOWNLOAD":
            do_download(sock, rfile, arg)
        else:
            # LOGIN, MSG, and anything unknown go to the server as-is,
            # so the server reports invalid commands itself.
            send_line(sock, f"{cmd}: {arg}" if arg else cmd)
            print(get_reply(rfile))


def main():
    try:
        host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    except ValueError:
        print("Usage: python3 client.py [host] [port]")
        return
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.settimeout(None)
    except OSError:
        print(f"Could not connect to server at {host}:{port}. Is it running?")
        return
    print(f"Connected to {host}:{port}. Type HELP for commands.")
    rfile = sock.makefile("rb")
    try:
        run(sock, rfile)
    except KeyboardInterrupt:
        print()
        try:
            send_line(sock, "QUIT")
        except OSError:
            pass
    except (OSError, ValueError) as e:
        print(f"Connection lost: {e}")
    finally:
        rfile.close()
        sock.close()
        print("Disconnected.")


if __name__ == "__main__":
    main()
