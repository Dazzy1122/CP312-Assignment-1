# CP372 Assignment 1 — TCP Messaging & File Transfer

A command-line client and server that communicate over raw TCP sockets using a custom text-based protocol. A client can log in, send text messages, list the server's files, and upload or download files of any type and size. The server handles one client at a time and keeps running after each client disconnects.

## Requirements

- Python 3.8 or newer
- No third-party packages. Only the standard library is used (`socket`, `os`, `sys`, `time`, `hashlib`, `json`).

Works on Windows, macOS and Linux. On Windows, use `python` instead of `python3` in the commands below.

## Folder Structure

```
CP312-Assignment-1/
├── server.py              # TCP server: accept loop, command handling, logging
├── client.py              # TCP client: interactive prompt
├── protocol.py            # Shared constants and send/receive helpers
├── users.txt              # Usernames allowed to log in, one per line
├── server_files/          # Files stored on the server
└── client_files/          # Files the client can upload
    └── downloads/         # Files the client downloads land here
```

The storage folders are created automatically if they don't exist.

## Running

Open two terminals in the project folder.

**1. Start the server**

```bash
python3 server.py [host] [port]
```

Both arguments are optional and default to `127.0.0.1` and `5000`.

```bash
python3 server.py                  # 127.0.0.1:5000
python3 server.py 0.0.0.0 6000     # all interfaces, port 6000
```

The server runs until you press **Ctrl+C**.

**2. Start the client**

```bash
python3 client.py [host] [port]
```

Use the same host and port as the server (defaults `127.0.0.1` and `5000`). To connect from another machine, pass the server's IP address and start the server with host `0.0.0.0`.

## Users

Only usernames listed in `users.txt` can log in. Add one name per line:

```
Ahmad
Danny
Tao
```

Usernames are case-sensitive. No password is required. Restart the server after editing this file.

## Commands

Type commands at the client's `> ` prompt. Command names are not case-sensitive.

| Command | Description | Login needed |
|---|---|---|
| `LOGIN <username>` | Log in as a user from `users.txt` | No |
| `MSG <text>` | Send a text message to the server | Yes |
| `LIST` | List files stored on the server, with sizes | Yes |
| `UPLOAD <filename>` | Send `client_files/<filename>` to the server | Yes |
| `DOWNLOAD <filename>` | Save the server's file to `client_files/downloads/<filename>` | Yes |
| `HELP` | Show the command list (handled by the client) | No |
| `QUIT` | Disconnect and exit | No |

Uploading or downloading a file with a name that already exists replaces the old copy.

## Example Session

Client:

```
Connected to 127.0.0.1:5000. Type HELP for commands.
> LOGIN Alice
OK: Welcome Alice
> MSG Hello Server
OK: Message received
> UPLOAD notes.txt
Uploading 'notes.txt' (12 bytes)...
OK: File 'notes.txt' uploaded (12 bytes)
> LIST
  notes.txt                                12 bytes
> DOWNLOAD notes.txt
Downloading 'notes.txt' (12 bytes)...
OK: Downloaded 'notes.txt' (12 bytes), checksum verified -> .../client_files/downloads/notes.txt
> DOWNLOAD missing.txt
ERROR: File 'missing.txt' not found
> QUIT
OK: Goodbye
Disconnected.
```

Server:

```
[14:02:11] [SERVER] Listening on 127.0.0.1:5000 (Ctrl+C to stop)
[14:02:15] [CLIENT CONNECTED] 127.0.0.1:53122
[14:02:18] [LOGIN] User 'Alice' logged in
[14:02:22] [MESSAGE RECEIVED] Alice: Hello Server
[14:02:30] [FILE RECEIVED] 'notes.txt' (12 bytes)
[14:02:35] [FILE SENT] 'notes.txt' (12 bytes)
[14:02:41] [ERROR] File not found: 'missing.txt'
[14:02:45] [CLIENT DISCONNECTED] 127.0.0.1:53122
```

## Protocol Summary

Full details are in the protocol documentation PDF.

- Every request and response header is one line of UTF-8 text ending in `\n`.
- Requests look like `COMMAND: argument`, for example `LOGIN: Alice` or `QUIT`.
- Responses start with `OK:` on success or `ERROR:` on failure, for example `OK: Welcome Alice` or `ERROR: Please LOGIN first`.
- File contents are sent as raw bytes right after a header giving the exact size and a SHA-256 checksum (`UPLOAD: name|size|sha256`, or `OK: size|sha256` for downloads), so any file type (text, images, PDFs, video) transfers byte-for-byte. The receiver verifies the checksum before saving.

| Request | Success reply | Possible errors |
|---|---|---|
| `LOGIN: <user>` | `OK: Welcome <user>` | Unknown user, Missing username |
| `MSG: <text>` | `OK: Message received` | Please LOGIN first, Empty message |
| `LIST` | `OK: [["name", size], ...]` | Please LOGIN first |
| `UPLOAD: <name>\|<size>\|<sha256>` | `OK: READY`, then after the bytes `OK: File '<name>' uploaded` | Please LOGIN first, Bad UPLOAD format, Checksum mismatch |
| `DOWNLOAD: <name>` | `OK: <size>\|<sha256>` followed by the bytes | Please LOGIN first, File not found |
| `QUIT` | `OK: Goodbye` | — |
| anything else | — | Invalid command |

## Error Handling

- Unknown commands, bad formats and commands sent before logging in get an `ERROR:` reply; the connection stays open.
- Uploading a file that doesn't exist in `client_files/` is caught by the client before anything is sent.
- If the server isn't running, the client prints a message and exits instead of crashing.
- If either side disconnects mid-transfer, the partial file is deleted and the server goes back to waiting for the next client.
- Filenames are stripped of directory parts, so `../../secret.txt` is saved as `secret.txt` inside the storage folder.

## Testing Without the Client

You can talk to the server directly with `nc` (netcat) and type raw protocol lines:

```bash
nc 127.0.0.1 5000
LOGIN: Alice
LIST
QUIT
```
