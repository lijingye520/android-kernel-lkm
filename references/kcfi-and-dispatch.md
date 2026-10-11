# KCFI 与厂商函数表 / KCFI and Vendor Function Tables

适用于「在别人的结构体里换回调」「按类型的槽位」「厂商按名字/编号分派的函数表」这类修改。
For modifying callbacks inside vendor structs, typed slot scanning, and vendor dispatch tables.

## 1. 校验通过 ≠ 调用安全 / Validated ≠ safe to call

`validate_kcfi()` 只比对入口前 4 字节的 type hash。它证明「签名对上了」，不证明：
`validate_kcfi()` only compares the 4-byte type hash before the entry. It proves the signature
matches. It does **not** prove:

- 这个函数会接受你的实参语义（结构体字段是否已经初始化）
  the function accepts your argument's *semantics* (are the struct fields initialized yet?)
- 该函数在你的调用上下文里是安全时机（设备初始化早期 vs 完全就绪后）
  the call happens at a safe time (early init vs fully up)
- 你从结构体里扫出来的那个槽位真的就是你想调的那个函数
  the slot you scanned really is the function you think it is

结构体里出现多个同签名指针是常态（厂商的 init/cleanup/各 stage 回调常常同型）。
Multiple same-signature pointers in one struct are normal (init/cleanup/stage callbacks are often
the same type). 扫描能给出「唯一匹配」才可以用；给出多个就必须换定位手段。
Only a *unique* match is usable; two or more matches means switch to another locating method.

## 2. 没有被取地址的函数没有 KCFI 前缀 / A function whose address is never taken has no KCFI prefix

Clang 只给「其地址被取出」的函数生成 `__kcfi_typeid_*` 前缀。厂商代码里只被直接调用、
从未取地址的 `static` 函数，入口前**没有** type hash：
Clang emits `__kcfi_typeid_*` only for functions whose address is taken. A vendor `static` function
that is only ever called directly and never has its address taken has **no** type hash before it:

```text
static void vendor_helper_a(struct vendor_ctx *ctx, int en);  // 只被同文件的分派函数直接调用
                                                              // only called directly by the dispatcher in the same file
=> read_kcfi_type() 读出的是相邻函数的代码字节，validate 必然失败
=> read_kcfi_type() returns code bytes of a neighbouring function; validation fails every time
```

症状：你按符号名解析到了正确地址，但 `validate_kcfi()` 返回 `-EINVAL`（`ret=-22`），
于是一个能用的旁路被自己的校验挡住。
Symptom: you resolved the right address by symbol name, but `validate_kcfi()` returns `-EINVAL`
(`ret=-22`) and your working fallback is blocked by your own check.

正确处理 / Correct handling:
- 先用别的证据确认地址正确（符号名 + 函数长度 + 首条指令 + 反汇编窗口对齐），再允许直调
  confirm the address another way (symbol name + size + first instructions + disassembly window), then call it directly
- 直调走一个 `__nocfi` 蹦床函数，避免自己的间接调用被 KCFI 拦
  call it through a `__nocfi` trampoline so your own indirect call isn't checked
- 把校验结果**记录下来**（日志打 `kcfi=%d`）而不是当成 hard gate——hash 缺失是预期的，不是错误
  log the result (`kcfi=%d`) instead of treating it as a hard gate; a missing hash is expected, not an error

## 3. 厂商分派层会在写任何东西之前 early-return / Vendor dispatch can return before doing anything

`obj->func(obj, handle, cmd, params)` 这种签名两侧都能对齐，但厂商在 switch 之前还有前置检查：
The signature on both sides can match while the vendor still has pre-switch guards:

```c
if (!obj) { pr_info("%s: error, obj=NULL!\n", __func__); return 0; }
if (obj->type != EXPECTED_TYPE) {                    // 前置检查 1 / guard 1
        pr_info("%s: obj = %s, return!\n", __func__, dump_type(obj));
        return 0;
}
...
case CMD_X: {
        struct vendor_ctx *inner = obj->inner;
        if (!inner) { pr_err("%s: inner is NULL\n", __func__); return; }   // 前置检查 2 / guard 2
        ...
}
```

**失败现象**：函数返回 0（成功），但副作用一个都没发生——标志位没置、计数器没动、结构体没变。
**Failure shape**: the call returns 0 (success) but none of the side effects happened — no flag
set, no counter moved, no struct change.

排查顺序 / Triage order:
1. 先看厂商自己的打印有没有出现（`obj = %s, return!` / `inner is NULL`）——所以要把厂商 log tag
   一起抓进日志，不能只 grep 自己模块名
   check whether the vendor's own print appeared — which is why the vendor log tags must be captured too
2. 打印调用点能拿到的字段值（对象类型、上层上下文指针、参数字段、引用计数），
   一条日志就能区分是哪一级早退
   print the fields visible at the call site (object type, parent context pointer, param fields,
   refcount) to pin the guard level
3. 时序问题（早期阶段上层上下文还没绑定）就**不要**在这一轮把失败当致命错误；把它降级成
   「延迟到真正能生效的时机」再操作，模块照常加载
   if it's a timing issue (parent context unbound at an early stage) don't fail this iteration;
   downgrade to "defer to when it can take effect" and let the module load

## 4. 分派层的枚举/编号可能整段位移 / Dispatch indices can shift as a block

厂商 `switch (cmd)` 用枚举常量，但**设备上那份模块**和**你编译用的头文件**可能不是同一版：
The vendor `switch (cmd)` uses enum constants, but the module on the device and the headers you
compile against may be different releases:

- 枚举中间增/删一个成员 → 其后所有编号 -1/+1，switch 跳转表全部错位
  one member added/removed in the middle → all later indices shift by one; the jump table lands wrong
- 症状：命令 A 打进命令 B 的 case，B 把参数当另一种类型解引用 → panic（例如把上下文结构体
  指针当成显示状态指针用）
  symptom: command A lands in command B's case; B reinterprets the argument → panic (e.g. treating a
  context struct pointer as a display state pointer)
- 症状：命令打进了另一个「存在但静默 return」的 case，成功返回但什么也没做
  symptom: it lands in another existing-but-silent case, returns success, does nothing

判断方法 / How to tell:
- 用设备真身的反汇编看 `switch` 跳转表基址，直接数出每个编号对应哪段代码
  read the jump table base in the device's own disassembly and count which code each index lands in
- 不要用「静态核对全部通过」推断编号正确——编号错位时静态核对一样通过
  do not infer correctness from "all static checks passed"; they pass with shifted indices too

规避方法（拿不到设备真身时）/ Mitigation when you can't get the device's own copy:
- 只用「两种编号下都无害」的命令：发原编号，若副作用没出现（用标志位/计数器判断）再发
  `原编号 - 1`；被误命中的那个 case 必须是你可以从结构体里置 NULL 的 no-op
  only use commands that are harmless under both numberings: send the original; if the side effect
  didn't show (check flags/counters), send `index - 1`; make the mis-landed case a no-op you can
  neutralize by nulling the struct field
- 把「不确认就不发」的破坏性命令（写指针、改状态、提交事务）挑出来排除掉，代价是功能少一块
  exclude destructive commands (pointer writes, state changes, commits) rather than guessing
- 拿到设备真身后，删掉旁路，改用真实编号
  once you have the device's real module, delete the fallback and use the real indices
