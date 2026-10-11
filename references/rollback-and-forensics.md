# 回滚、日志与故障取证 / Rollback, Logging and Forensics

运行时挂钩类模块最常见的现场是「设备重启了、模块自我禁用了」，而日志包里只剩自己模块的
几行打印。这一篇讲怎么让每次失败都自带下一次需要的证据。
The usual runtime-hook failure looks like "device rebooted, module self-disabled" with a log bundle
containing only a few lines from your own module. This is how to make each failure carry the
evidence the next iteration needs.

## 1. 失败回滚必须还原所有被替换的指针 / Rollback must restore every replaced pointer

最常见的 use-after-free：把你替换进厂商结构体的那个指针（例如某回调、某参数表）指向模块
里的静态数据，init 中途失败返回，`module_put()` 后模块内存卸载，而厂商驱动仍持有那个指针
并在中断里读它。
The classic use-after-free: point a pointer you injected into a vendor struct (a callback, a params
table) at static data inside the module, fail mid-init, let `module_put()` unload the module's
memory, and the vendor driver still reads that pointer from an interrupt.

```c
/*
 * 失败路径顺序：先摘回调，再把指针指回厂商原值，最后才 module_put()
 * Failure path order: unhook callbacks, restore pointers to vendor originals, then module_put()
 */
rollback:
        remove_injected_nodes();                      /* 摘掉自己加的链表节点 / drop added list nodes */
        WRITE_ONCE(state.installed, false);
        WRITE_ONCE(vendor_obj->params_ptr, state.original_params);   /* 关键 / the critical one */
        WRITE_ONCE(other_obj->funcs, state.original_funcs);
        WRITE_ONCE(vendor_obj->funcs, state.original_vendor_funcs);
        rebuild_vendor_caches();                      /* 让厂商侧缓存重建 / rebuild vendor caches */
put_ref:
        module_put(THIS_MODULE);
        return ret;
```

自引用（`try_module_get(THIS_MODULE)`）能挡住 `rmmod`，但**挡不住 init 失败返回**——
那条路径照样会卸载。别把「有自引用」当成不用还原的理由。
A self-reference (`try_module_get(THIS_MODULE)`) blocks `rmmod` but does **not** block a failed
init return — that path unloads anyway. Don't treat the self-ref as a reason to skip restoration.

## 2. 回调失败时，先区分「脏数据」还是「检查过头」/ Distinguish stale data from an over-strict check

第一次上真机时常见：函数被调到了，但传进去的数据是上一轮的、检查因此拒绝。
On first real-device runs a common pattern: the callback fires, but the data it inspects is stale,
so your own validation rejects it.

典型现象：回调里打印出来的入参 `cur_mode` 是个指针残值、或者等于缓冲区地址之类的垃圾值。
Typical symptom: the callback's own log shows `cur_mode` as a pointer remnant or a buffer address.

处理 / Handling:
- 先把**入参**打出来（不是只打返回值），确认是「调用方给错了」还是「我没看懂」
  log the **arguments**, not just the return value, to tell "caller passed garbage" from "I misunderstood"
- 调用方给错时不要硬 `-EINVAL` 直接失败退出——先判断是不是可以在这一轮降级为 no-op 并让模块
  保持可用（模式还能用、只是不加速）
  when the caller does pass garbage, don't hard-fail with `-EINVAL`; downgrade to a no-op this round
  and keep the module usable (modes still work, just not boosted)
- 真的需要拒绝时，拒绝要发生在**注册前**（静态核对阶段），而不是运行中的热路径
  if you do need to reject, reject before registration (static phase), not on the hot path

## 3. 观察期日志：把厂商输出一起抓 / Capture vendor output too

只 grep 自己模块名 = 丢掉厂商的 early return 原因（见 `kcfi-and-dispatch.md` §3）。
Grepping only your own module name throws away the vendor's early-return reason.

```sh
# 抓自己 + 厂商框架的 tag / capture your own plus the vendor framework tags
dmesg | grep -E 'your_module|<vendor-framework-tags>' | tail -n 80
```

`boot.log` 用 `dmesg | grep <自己模块>` 抓的话，厂商行会在写日志前就被过滤掉，事后无法补。
If `boot.log` is produced with `dmesg | grep <your module>`, the vendor lines are filtered out at
capture time and cannot be recovered later.

## 4. 崩溃取证 / Crash forensics

带 mrdump / pstore 的设备，模块崩溃重启后仍能拿到上一轮的栈：
Devices with mrdump / pstore keep the previous boot's stack readable after a crash+reboot:

```sh
ls /sys/fs/pstore/
cat /sys/fs/pstore/console-ramoops-0 | tail -200
# 关键行 / key lines: "Unable to handle kernel NULL pointer dereference", "Call trace:", "pc :"
```

栈里的 `symbol+0xNNN/0xMMM` 里 `0xMMM` 是**到下一个符号的距离**（kallsyms 间距），
**不是** `nm` 报的 `st_size`。别用 `nm -S` 的 size 去否认「这是不是同一份模块」。
In a stack line `symbol+0xNNN/0xMMM`, `0xMMM` is the distance to the next symbol (kallsyms spacing),
**not** the `st_size` reported by `nm`. Don't use `nm -S` sizes to argue "this is not the same module".

```bash
# 用符号间距核对 / verify with symbol spacing
llvm-nm -n --defined-only <vendor>.ko | grep -A1 '<symbol-from-the-stack>'
# 相邻两符号地址之差 == 栈里的 0xMMM 时，说明栈就是这份模块
# when the gap between adjacent symbols equals 0xMMM, the stack belongs to this module
```

模块自己也可以带一个「上一轮崩溃证据」收集：把 pstore、`ro.boot.bootreason`、
`sys.boot.reason` 落到模块目录，配合 `load_in_progress` 守卫实现「崩了就自禁用，避免连环重启」。
The module can also collect its own previous-boot evidence: dump pstore, `ro.boot.bootreason`,
`sys.boot.reason` into the module directory, with a `load_in_progress` guard so a crash self-disables
instead of looping reboots.

## 5. 刷入循环要有退出条件 / Make the flash cycle terminate

实机迭代是「改 → 编译 → 刷入 → 抓日志」，很容易变成无脑重试。定好退出条件：
Real-device iteration is "edit → build → flash → pull log" and easily becomes blind retrying.
Define the stopping condition:

- 同一现象连续两轮没变化 → 停下来静态分析，不要继续刷
  same symptom unchanged for two rounds → stop and analyze statically, don't keep flashing
- 每次只改一个变量（一个偏移、一个命令号、一个钩子点），否则日志无法归因
  change exactly one variable per round (one offset, one command index, one hook point)
- 崩溃进自禁用状态时，先读 `crash-evidence` 再清标记，别直接删 `disable` 重刷
  when it self-disabled after a crash, read `crash-evidence` before clearing the flag
- 记录每轮 KO 的 `sha256` 并在日志里打印，事后才能确认设备跑的到底是哪一版
  record each round's KO `sha256` and print it in the log, so the flashed build is identifiable later
