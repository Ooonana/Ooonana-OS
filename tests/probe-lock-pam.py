#!/usr/bin/env python3
"""Real vendor i3lock PAM stack; public disposable test credential only."""
import ctypes as C
import os
import sys

assert os.getuid() == 1000 and os.environ.get("OOONANA_LOCK_AUTH_QA") == "1"
password = b"Ooonana-private-lock-QA-20261023"
if "--wrong" in sys.argv:
    password = b"Wrong-disposable-lock-QA-password"


class Message(C.Structure):
    _fields_ = [("style", C.c_int), ("text", C.c_char_p)]


class Response(C.Structure):
    _fields_ = [("text", C.c_void_p), ("code", C.c_int)]


Callback = C.CFUNCTYPE(C.c_int, C.c_int, C.POINTER(C.POINTER(Message)), C.POINTER(C.POINTER(Response)), C.c_void_p)
libc = C.CDLL(None)
libc.calloc.argtypes, libc.calloc.restype = [C.c_size_t, C.c_size_t], C.c_void_p
libc.strdup.argtypes, libc.strdup.restype = [C.c_char_p], C.c_void_p


@Callback
def converse(count, messages, output, _data):
    if not 0 < count <= 32:
        return 19  # PAM_CONV_ERR
    memory = libc.calloc(count, C.sizeof(Response))
    if not memory:
        return 5  # PAM_BUF_ERR
    responses = C.cast(memory, C.POINTER(Response))
    for index in range(count):
        style = messages[index].contents.style
        if style in (1, 2):
            responses[index].text = libc.strdup(password if style == 1 else b"ooonana")
    output[0] = responses  # PAM owns/frees allocated response array and strings.
    return 0


class Conversation(C.Structure):
    _fields_ = [("callback", Callback), ("data", C.c_void_p)]


pam = C.CDLL("libpam.so.0")
pam.pam_start.argtypes = [C.c_char_p, C.c_char_p, C.POINTER(Conversation), C.POINTER(C.c_void_p)]
pam.pam_authenticate.argtypes = [C.c_void_p, C.c_int]
pam.pam_end.argtypes = [C.c_void_p, C.c_int]
handle = C.c_void_p()
conversation = Conversation(converse, None)
result = pam.pam_start(b"i3lock", b"ooonana", C.byref(conversation), C.byref(handle))
try:
    if result == 0:
        result = pam.pam_authenticate(handle, 0)
    expected = "--expect-success" in sys.argv
    assert (result == 0) == expected, ("PAM result", result, "expected success", expected)
    print("LOCK_PAM_OK", "accepted" if result == 0 else "rejected", "code", result)
finally:
    if handle:
        pam.pam_end(handle, result)
