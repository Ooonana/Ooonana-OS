"""Bounded read-only i3 IPC subscriptions for desktop status rendering."""
import json
import os
import socket
import struct
import subprocess

MAGIC = b"i3-ipc"
HEADER = struct.Struct("=6sII")
MAX_MESSAGE = 4 * 1024 * 1024


def socket_path():
    return os.environ.get("I3SOCK") or subprocess.check_output(["i3", "--get-socketpath"], text=True, timeout=3).strip()


def receive_exact(connection, length):
    result = bytearray()
    while len(result) < length:
        block = connection.recv(length - len(result))
        if not block:
            raise EOFError("i3 disconnected")
        result.extend(block)
    return bytes(result)


def receive(connection):
    magic, size, kind = HEADER.unpack(receive_exact(connection, HEADER.size))
    if magic != MAGIC or size > MAX_MESSAGE:
        raise ValueError("Invalid i3 IPC frame")
    return kind, json.loads(receive_exact(connection, size))


def send(connection, kind, payload=b""):
    connection.sendall(HEADER.pack(MAGIC, len(payload), kind) + payload)


def request(path, kind):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(path)
        send(connection, kind)
        reply_kind, value = receive(connection)
        if reply_kind != kind:
            raise ValueError("Unexpected i3 reply")
        return value


def trees():
    path = socket_path()
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(path)
        send(connection, 2, b'["window","workspace","output","shutdown"]')
        kind, reply = receive(connection)
        if kind != 2 or not reply.get("success"):
            raise ValueError("i3 subscription failed")
        connection.settimeout(None)
        yield request(path, 4)
        while True:
            kind, _event = receive(connection)
            if kind == 0x80000006:
                return
            if kind & 0x80000000:
                yield request(path, 4)
