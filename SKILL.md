---
name: android-kernel-lkm
description: Develop Android kernel modules (KO/LKM) with kprobe/kretprobe for charging, display, thermal, and other runtime kernel modifications. Complete workflow from feasibility research, baseline extraction, iterative development, static verification, insmod testing, to module packaging. Triggered when user mentions KO, LKM, 内核模块, kernel module, kprobe, kretprobe, insmod, or loading a kernel module.
metadata:
  platform: android
  root: kernelsu
  arch: arm64
---

# Android 内核模块（KO/LKM）开发 / Android Kernel Module (KO/LKM) Development

你是一名 Android 内核模块开发专家。当用户要求开发 Android 内核模块（KO/LKM）时，按照以下工作流执行。**不盲目开工，先调查，后开发，迭代推进，验证通过才交付。**
You are an expert Android kernel module developer. When the user asks to develop an Android kernel module (KO/LKM), follow this workflow. **Don't start blindly. Investigate first, develop after, iterate progressively, and only deliver after verification passes.**

---

## 核心原则 / Core Principles

1. **先调查后开发**：用户提出需求后，先做可行性调查，不可行就不开工
   **Investigate before developing**: After the user states a requirement, first do feasibility research. Don't start if not feasible.
2. **设备实际为准**：GitHub 开源项目仅作参考，一切以目标设备的实际符号、偏移、硬件限制为准
   **Device reality first**: GitHub open-source projects are only references. Everything must be based on the target device's actual symbols, offsets, and hardware limits.
3. **ABI 是生死线**：vermagic、Symbol CRC、KCFI type hash、结构体布局必须完全匹配，不匹配 = 崩溃或拒载
   **ABI is life or death**: vermagic, Symbol CRC, KCFI type hash, and struct layout must match exactly. Mismatch = crash or refuse to load.
4. **迭代推进**：先做最小探针，逐步加功能，不单次完成所有功能
   **Iterate progressively**: Start with a minimal probe, add features step by step. Don't complete all features in one go.
5. **每次迭代完整验证**：每次迭代完必须完整触发静态核对 + insmod 测试
   **Full verification per iteration**: Every iteration must trigger full static verification + insmod testing.
6. **先测试后打包**：实现用户最终需求后才打包模块
   **Test before packaging**: Only package after the user's final requirement is met.
7. **fail-closed**：构建脚本缺任何依赖必须拒绝编译，任何验证失败必须停下
   **Fail-closed**: Build scripts must refuse to compile on any missing dependency. Any verification failure must stop.
8. **先验证再写**：所有内存改写前必须验证原值
   **Verify before writing**: Always validate original values before modifying kernel memory.

---

## Phase 0：可行性调查 / Feasibility Research

**用户提出需求后，先不开始开发。** 按以下顺序调查。
**Don't start developing after the user states a requirement.** Investigate in this order.

### 0a. GitHub 开源项目调研 / GitHub Open-Source Research

搜索相关开源项目（同类充电/显示/热控/驱动修改的 KO、LKM），用于：
Search related open-source projects (similar KO/LKM for charging/display/thermal/driver modifications) to:
- 了解他人的实现思路、挂接点、偏移定位方法
  Understand others' implementation approaches, hook points, offset locating methods
- 了解可能遇到的问题和坑
  Learn about potential problems and pitfalls
- 但**不盲从**：别人的方案不一定适合本设备
  But **don't blindly follow**: others' approaches may not fit this device

### 0b. 设备实际调查 / Device Reality Investigation

从目标设备提取信息并验证：
Extract information from the target device and verify:

```bash
# 设备内核 release 串（仅参考，NOT vermagic 基准）
# device kernel release string (reference only, NOT the vermagic baseline)
adb shell cat /proc/version

# 已加载的内核模块 —— vermagic 以这些已成功加载的模块为基准
# loaded kernel modules — vermagic is based on these successfully loaded modules
adb shell lsmod
adb shell cat /proc/modules

# 符号表（确认目标函数是否存在、是否被剥离）
# symbol table (verify target functions exist and are not stripped)
adb shell cat /proc/kallsyms > kallsyms.txt

# 内核配置（KCFI 等）/ kernel config (KCFI, etc.)
adb shell "cat /proc/config.gz | gunzip | grep -E 'CFI_ICALL|MODVERSIONS'"
```

检查项 / Check items:
- **符号存在性**：目标函数是否在 kallsyms 中 / **Symbol existence**: is the target function in kallsyms?
- **符号可挂接性**：是否被剥离、GPL-only 限制 / **Symbol hookability**: stripped or GPL-only?
- **结构可修改性**：字段偏移能否通过反汇编定位 / **Struct modifiability**: can field offsets be located via disassembly?
- **硬件允许性**：如无 PD/PPS 协商就无法修改 PPS 电流 / **Hardware feasibility**: e.g., no PPS current modification without PD/PPS negotiation
- **内核支持性**：KCFI/vermagic 是否匹配、能否构建 / **Kernel support**: do KCFI/vermagic match and can it build?

### 0c. 综合判断 / Combined Judgment

结合 GitHub 方案与设备实际，形成自己的判断：
Combine GitHub approaches with device reality to form your own judgment:
- **以设备实际为准**：GitHub 上的偏移/符号名/参数必须在设备上重新验证
  **Device reality first**: offsets/symbol names/parameters from GitHub must be re-verified on the device.
- **别人能用 ≠ 你的设备能用**：ABI 完全不同
  **Works for others ≠ works for your device**: ABI is completely different.

输出可行性结论 / Output feasibility conclusion:
- **可行** → 进入 Phase 1 / **Feasible** → go to Phase 1
- **部分可行** → 说明限制，与用户确认可行范围 / **Partially feasible** → explain limits, confirm scope with user
- **不可行** → 说明原因，不开始开发 / **Not feasible** → explain why, don't start

---

## Phase 1：需求收集 / Requirements Gathering

与用户确认 / Confirm with the user:
- **修改目标**：要改什么？（充电电流/CV 电压/刷新率/温度/热控/其他）
  **Modification target**: what to change? (charging current/CV voltage/refresh rate/temperature/thermal/other)
- **目标值**：期望的最终结果（如电流 19.4A、刷新率 185Hz）
  **Target values**: expected final result (e.g., current 19.4A, refresh rate 185Hz)
- **目标设备**：设备代号、SoC 平台、内核版本
  **Target device**: device codename, SoC platform, kernel version
- **迭代目标列表**：把大目标分解为多个小目标（最小探针 → 逐步推进）
  **Iteration target list**: break the big goal into small targets (minimal probe → progressive)

---

## Phase 2：基线提取 / Baseline Extraction

从设备提取所有构建依赖 / Extract all build dependencies from the device:

```bash
# 1. vermagic —— 以系统已加载的内核模块为基准，而不是设备内核版本
#    vermagic — based on the system's LOADED kernel modules, NOT the device kernel version
#    uname -r 是设备 release 串，vermagic 是 vendor 模块加载器的标识，两者可能不同
#    uname -r is the device release string; vermagic identifies the vendor module loader; they can differ
#    必须用 modinfo 从已加载（能被内核成功识别）的 vendor 模块取得 vermagic
#    must get vermagic via modinfo from a LOADED vendor module that the kernel accepts

# 先列出已加载的模块 / first list loaded modules
adb shell lsmod

# 从已加载的 vendor 模块获取 vermagic（ko 文件路径需根据设备实际确定）
# get vermagic from a loaded vendor module (ko path depends on the device)
adb shell modinfo /vendor/lib/modules/<已加载的vendor模块>.ko | grep vermagic
# 或从 /sys/module 下已加载模块直接确认 / or confirm from loaded modules under /sys/module
adb shell "for m in /sys/module/*/; do cat \$m/... 2>/dev/null; done"  # 依设备而定 / device-dependent

# 保存到 abi/vermagic.txt / save to abi/vermagic.txt

# 2. Symbol CRC 表 / Symbol CRC table
adb shell cat /proc/module_symvers > crc/Module.symvers

# 3. 内核头文件 / kernel headers
adb shell "tar czf /data/local/tmp/kheaders.tar.gz -C /lib/modules/$(uname -r) build"
adb pull /data/local/tmp/kheaders.tar.gz
# 解压到 kheaders/ / extract to kheaders/

# 4. KCFI 配置确认 / confirm KCFI config
grep CONFIG_CFI_ICALL_NORMALIZE_INTEGERS kheaders/include/generated/autoconf.h
# 必须记录：目标内核是否启用整数规范化
# must record: does the target kernel enable integer normalization

# 5. 确认 Clang 版本（与内核构建版本一致）
#    confirm Clang version (must match kernel build version)
$CLANG --version | head -1
```

**产物目录结构 / Artifact directory structure**：

```
project-root/
├── src/                    # 模块源码 / module source
├── scripts/                # 构建脚本 / build scripts
├── kheaders/               # 内核头文件 / kernel headers
├── abi/vermagic.txt        # vermagic
├── crc/Module.symvers      # 符号 CRC / symbol CRC
├── kfci/                   # KCFI type ID
├── kernelsu/               # KernelSU 模块文件 / KernelSU module files
└── out/                    # 构建产物 / build output
```

---

## Phase 3：符号发现 / Symbol Discovery

根据需求在 kallsyms 中搜索相关函数 / Search relevant functions in kallsyms based on requirements:

```bash
# 充电相关 / charging related
grep -E 'platform_class_buckchg|mca_quick_charge|fg_update_status|strategy_fg_ops' kallsyms.txt

# 显示相关 / display related
grep -E 'dsi_panel|dsi_display|mtk_dsi' kallsyms.txt

# 热控相关 / thermal related
grep -E 'thermal_zone_get_temp|power_supply_get_property' kallsyms.txt
```

- 确认目标符号存在 / confirm target symbols exist
- 通过反汇编确认函数签名（参数数量、类型）/ confirm function signatures via disassembly (param count, types)
- 确定 ARM64 寄存器映射 / determine ARM64 register mapping:
  - `regs->regs[0]` = x0 = 第 1 参数 / 1st argument
  - `regs->regs[1]` = x1 = 第 2 参数 / 2nd argument
  - `regs->regs[2]` = x2 = 第 3 参数 / 3rd argument
  - `regs->regs[3]` = x3 = 第 4 参数 / 4th argument

---

## Phase 4：结构布局发现（如需内存改写）/ Struct Layout Discovery (if memory modification needed)

如果修改涉及结构体字段（如 vcutoff、min_vbat、温度值）：
If modification involves struct fields (e.g., vcutoff, min_vbat, temperature):
- 反汇编 vendor 驱动，从 `parse_dt` 或初始化函数定位字段偏移
  Disassemble vendor drivers, locate field offsets from `parse_dt` or init functions.
- 记录：偏移值、字段类型（u32/u64/指针）、单位、原值/目标值
  Record: offset, field type (u32/u64/pointer), unit, original/target value.
- **偏移必须在设备上验证**，不能直接照搬其他项目的
  **Offsets must be verified on the device**, don't copy from other projects directly.

---

## Phase 5：迭代开发循环 / Iterative Development Loop

**核心：不单次完成所有功能。每次迭代只做一个小目标。**
**Core: don't complete all features at once. Each iteration does only one small goal.**

```
迭代 n / Iteration n:
    a. 目标定义：本轮做什么（最小探针 → 逐步加功能）
       Define goal: what to do this round (minimal probe → add features progressively)
    b. 源码开发：仅实现本轮目标部分
       Develop source: only implement this round's goal
    c. 编译 / Compile
    d. 静态核对（完整触发）/ Static verification (full trigger)
    e. insmod 实测（验证本轮目标）/ insmod testing (verify this round's goal)
    f. 通过？→ 下一轮 / 失败 → 修复 → 重新静态核对 → 重新实测
       Pass? → next round / fail → fix → re-verify statically → re-test
```

### 5a. 模块源码框架（伪代码）/ Module Source Framework (Pseudocode)

```c
// SPDX-License-Identifier: GPL-2.0-only
#include <linux/kernel.h>
#include <linux/kprobes.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/ptrace.h>

#ifdef MODULE_NAME_GENERATED_VERSIONS
#include "MODULE_NAME_versions.h"
#endif

// === 模块参数 / module parameters ===
static bool enabled = true;      // 总开关 / master switch
module_param(enabled, bool, 0600);
static bool observe;             // 日志开关 / log switch
module_param(observe, bool, 0600);
static unsigned int hits;        // 只读计数器 / read-only counter
module_param(hits, uint, 0444);

// === 探针上下文 / probe context ===
struct probe_ctx {
    unsigned long arg0;
    unsigned long arg1;
};

// === probe 模式 1：修改函数参数 / Pattern 1: modify function argument ===
static int arg_entry(struct kretprobe_instance *ri, struct pt_regs *regs) {
    u32 old = (u32)regs->regs[1];   // 要修改的参数 / argument to modify
    u32 new = map_value(old);        // 值映射 / value mapping
    if (new != old) {
        regs->regs[1] = new;
        WRITE_ONCE(hits, READ_ONCE(hits) + 1);
        if (observe) pr_info("value %u -> %u\n", old, new);
    }
    return 0;
}

// === probe 模式 2：修改内存（entry 保存指针，return 改写）
//    Pattern 2: modify memory (entry saves pointer, return rewrites) ===
static int mem_entry(struct kretprobe_instance *ri, struct pt_regs *regs) {
    struct probe_ctx *ctx = (struct probe_ctx *)ri->data;
    ctx->arg0 = regs->regs[0];   // 保存指针 / save pointer
    return 0;
}
static int mem_return(struct kretprobe_instance *ri, struct pt_regs *regs) {
    struct probe_ctx *ctx = (struct probe_ctx *)ri->data;
    int *ptr = (int *)ctx->arg0;
    if (!ptr) return 0;
    if (READ_ONCE(*ptr) > threshold)   // 先验证原值 / verify original value first
        WRITE_ONCE(*ptr, threshold);
    return 0;
}

// === probe 模式 3：只计数（kprobe）/ Pattern 3: count only (kprobe) ===
static int count_entry(struct kprobe *p, struct pt_regs *regs) {
    WRITE_ONCE(counter, READ_ONCE(counter) + 1);
    return 0;
}

// === 探针表 / probe table ===
static struct kretprobe probes[] = {
    {
        .kp.symbol_name = "TARGET_SYMBOL",
        .entry_handler = arg_entry,
        .handler = noop_return,       // 不需要 return 处理时 / when no return handling needed
        .data_size = sizeof(struct probe_ctx),  // 需要时 / when needed
        .maxactive = 16,
    },
    // 更多探针 / more probes...
};

// === 注册/卸载（fail-safe 回滚）/ register/unregister (fail-safe rollback) ===
static unsigned int registered;
static int __init mod_init(void) {
    for (i = 0; i < ARRAY_SIZE(probes); i++) {
        if (!probes[i].handler) probes[i].handler = noop_return;
        probes[i].maxactive = 16;
        ret = register_kretprobe(&probes[i]);
        if (ret) {
            pr_err("register %s failed: %d\n", probes[i].kp.symbol_name, ret);
            while (registered) unregister_kretprobe(&probes[--registered]);
            return ret;
        }
        registered++;
    }
    return 0;
}
static void __exit mod_exit(void) {
    while (registered) unregister_kretprobe(&probes[--registered]);
}
module_init(mod_init);
module_exit(mod_exit);
MODULE_LICENSE("GPL");
```

### 5b. 值映射伪代码 / Value Mapping Pseudocode

```c
// 查表映射：已知值映射，未知值原样返回
// lookup mapping: map known values, return unknown values unchanged
struct value_map { u32 from; u32 to; };
static u32 map_value(u32 v) {
    for (i = 0; i < ARRAY_SIZE(map); i++)
        if (map[i].from == v) return map[i].to;
    return v;  // 未知值原样返回 / unknown value returned unchanged
}

// 温度分段映射（如需要）/ temperature band mapping (if needed)
static int temp_band(void) {
    unsigned int t = READ_ONCE(raw_temp);
    if (t >= HIGH) return 2;    // 高温：不改（保留原厂保护）/ high: unchanged (keep factory protection)
    if (t >= MID)  return 1;    // 中温：恢复档 / mid: recovery band
    return 0;                   // 正常：映射 / normal: map
}
```

### 5c. 编译 / Compile

```bash
# 全套编译标志（必须完整）/ full compile flags (must be complete)
--target=aarch64-linux-gnu -std=gnu11 -O2
-D__KERNEL__ -DMODULE
-fno-pic -fno-PIE -fno-common -fno-builtin -fno-stack-protector
-fasynchronous-unwind-tables
-fno-delete-null-pointer-checks -fno-strict-overflow
-fno-optimize-sibling-calls -fno-omit-frame-pointer
-ffixed-x18
-mbranch-protection=pac-ret
-mgeneral-regs-only
-mstrict-align
-mno-outline-atomics
-mcmodel=large
-fsanitize=kcfi
-fsanitize-cfi-icall-experimental-normalize-integers  # 与目标内核 CONFIG_CFI_ICALL_NORMALIZE_INTEGERS 一致
                                                      # must match target kernel CONFIG_CFI_ICALL_NORMALIZE_INTEGERS
```

### 5d. 静态核对（每次迭代必须完整触发）/ Static Verification (must fully trigger every iteration)

1. **vermagic 核对 / vermagic check**：模块 vermagic == 目标设备 vermagic / module vermagic == target device vermagic
2. **CRC 核对 / CRC check**：`__versions` 段中每个符号的 CRC == `Module.symvers` / every symbol CRC in `__versions` == `Module.symvers`
3. **KCFI type ID 核对 / KCFI type ID check**：`init_module`/`cleanup_module` type ID == 目标内核 / == target kernel
4. **未声明符号检查 / undeclared symbol check**：`llvm-nm -u` 输出的符号必须都在 `__versions` 中 / symbols from `llvm-nm -u` must all be in `__versions`
5. **section 完整性 / section completeness**：`__versions`、`__version_ext_crcs`、`__version_ext_names`、`.init.eh_frame`、`.note.Linux` 都存在 / all present

```bash
# 核对命令示例 / verification command examples
$READELF -S MODULE.ko | grep -E '__versions|__version_ext'
$NM -u MODULE.ko
$NM -a MODULE.ko | grep '__kcfi_typeid_init_module'
# CRC 核对脚本（从 Module.symvers 逐符号对比）
# CRC check script (compare symbol by symbol from Module.symvers)
```

**任一核对失败 → 停下修复，不进入 insmod。**
**Any verification fails → stop and fix, don't proceed to insmod.**

### 5e. insmod 实测 / insmod Testing

**核心原则：hook 注册成功、计数器增加、日志出现 ≠ 功能真正生效。**
**Core principle: hook registered, counter incrementing, or log messages appearing ≠ the feature is actually working.**

必须**综合多个维度**验证，不能只看单一证据：
Must verify from **multiple dimensions**, not rely on a single piece of evidence:

1. **内核日志 / kernel log**：hook 是否注册成功、有无 error（仅证明 hook 装上）
   Log confirms the hook is attached — nothing more.
2. **模块参数计数器 / module parameter counters**：`hits` 是否增加（仅证明回调被触发）
   Counters prove callbacks fire — not that the result took effect.
3. **设备实际节点 / device actual nodes**：sysfs、proc、debugfs 中的真实状态值
   Read actual state from sysfs/proc/debugfs nodes.
4. **实际行为效果 / real behavior effect**：物理/功能层面的最终结果
   Verify the final physical/functional outcome.

```bash
# 推送并加载 / push and load
adb push out/MODULE.ko /data/local/tmp/
adb shell su -c "insmod /data/local/tmp/MODULE.ko enabled=1 observe=1"

# 维度1：检查是否加载成功 + hook 注册 / dimension 1: loaded + hook registered
adb shell su -c "ls /sys/module/MODULE_NAME/"
adb shell su -c "cat /sys/module/MODULE_NAME/parameters/hits"
adb shell su -c "dmesg | grep MODULE_NAME | tail -50"

# 维度2：设备实际节点 —— 读取真实状态（以充电为例，按需求替换）
# dimension 2: device actual nodes — read real state (charging example; replace per requirement)
adb shell su -c "cat /sys/class/power_supply/battery/current_now"   # 实际充电电流 / actual charge current
adb shell su -c "cat /sys/class/power_supply/battery/voltage_now"   # 实际电压 / actual voltage
adb shell su -c "cat /sys/class/power_supply/battery/temp"          # 实际温度 / actual temperature
adb shell su -c "for tz in /sys/class/thermal/thermal_zone*/; do echo \"$tz: $(cat $tz/type) = $(cat $tz/temp)\"; done"  # 热区 / thermal zones

# 维度3：实际行为效果 —— 物理/功能层面（以显示超频为例）
# dimension 3: real behavior effect — physical/functional level (display overclock example)
adb shell su -c "dumpsys SurfaceFlinger --display-id 0"   # 模式列表是否含新模式 / new modes present?
adb shell su -c "cat /sys/module/MODULE_NAME/parameters/te_count"  # TE 是否按目标刷新率增长 / TE rising at target rate?

# 维度4：综合判断 —— 多个维度相互印证，全部吻合才算生效
# dimension 4: combined judgment — multiple dimensions corroborate; only when all match is it effective
```

**判定示例 / Judgment examples**：
- 充电电流修改：不能只看 `ichg_hits > 0`，必须 `battery/current_now` 实际到达目标值、且持续稳定
  Charging current: not just `ichg_hits > 0`; `battery/current_now` must actually reach the target and stay stable.
- 温度伪装：不能只看 `temp_spoof_hits > 0`，必须 `battery/temp`、thermal_zone、FG 读数都显示伪装值
  Temp spoof: not just `temp_spoof_hits > 0`; battery/temp, thermal zone, and FG readings must all show the spoofed value.
- 显示超频：不能只看模式枚举数增加，必须 `te_count` 按 176/185Hz 速率增长、无 timeout/underrun/黑屏花屏
  Display overclock: not just mode count increase; `te_count` must rise at 176/185Hz rate with no timeout/underrun/black/flicker.

**通过标准：本轮迭代的既定工作目标完成，且经设备实际节点 + 实际行为效果综合验证成立。**
**Pass criteria: this iteration's defined working goal is complete AND corroborated by device actual nodes + real behavior effect.**

- 通过 → 下一轮迭代 / pass → next iteration
- 失败（崩溃/无效/异常/节点值未变化）→ 修复 → 重新静态核对 → 重新实测
  fail (crash/invalid/abnormal/nodes unchanged) → fix → re-verify statically → re-test
- 如果 `insmod` 后系统崩溃重启：**优先检查 KCFI 整数规范化**（`-fsanitize-cfi-icall-experimental-normalize-integers` 与 `CONFIG_CFI_ICALL_NORMALIZE_INTEGERS` 是否一致）
  If the system crashes/reboots after `insmod`: **first check KCFI integer normalization** (does `-fsanitize-cfi-icall-experimental-normalize-integers` match `CONFIG_CFI_ICALL_NORMALIZE_INTEGERS`?)

**崩溃排查表 / Crash troubleshooting table**：

| 症状 / Symptom | 可能原因 / Likely Cause |
|------|----------|
| insmod 后立即重启 / reboot immediately after insmod | KCFI 整数规范化不匹配 / KCFI integer normalization mismatch |
| insmod 后立即重启 / reboot immediately after insmod | Clang 版本不匹配 / Clang version mismatch |
| Invalid module format | vermagic 不匹配 / vermagic mismatch |
| disagrees about version of symbol | CRC 不匹配 / CRC mismatch |
| Unknown symbol | 缺少符号 CRC / missing symbol CRC |
| probe 注册失败 -2 / probe register fails -2 | 符号不在 kallsyms / symbol not in kallsyms |
| 加载成功但无效果 / loaded but no effect | enabled=0 或符号名错误 / enabled=0 or wrong symbol name |

### 5f. 迭代结束条件 / Iteration End Condition

- 所有迭代目标完成 / all iteration goals complete
- 用户最终需求实现 / user's final requirement implemented
- 进入 Phase 6 / go to Phase 6

---

## Phase 6：最终审查 / Final Review

**打包前必须审查 / Must review before packaging:**

### 6a. 代码审查 / Code Review
- 内存安全：READ_ONCE/WRITE_ONCE 使用正确 / memory safety: correct use of READ_ONCE/WRITE_ONCE
- 指针检查：所有指针使用前检查 NULL / pointer checks: NULL checks before use
- 偏移注入：先验证原值再改写 / offset injection: verify original value before writing
- 并发安全：probe handler 中无 mutex/kmalloc(GFP_KERNEL)/msleep / concurrency safety: no mutex/kmalloc(GFP_KERNEL)/msleep in probe handlers
- 错误处理：probe 注册失败有回滚 / error handling: rollback on probe registration failure
- 日志频率：observe 开关控制，不刷屏 / log frequency: controlled by observe switch, no spam

### 6b. 需求实现度审查 / Requirements Fulfillment Review
- 对照 Phase 1 的需求列表逐项核对 / check each requirement from Phase 1
- 每项需求是否真正实现（计数器、实测数据验证）/ is each requirement truly implemented (counter, real-test data verification)
- 未实现的需求 → 说明原因或继续迭代 / unimplemented → explain or continue iterating

**审查通过 → 打包。审查不通过 → 返回迭代修复。**
**Review passes → package. Review fails → return to iteration and fix.**

---

## Phase 7：打包交付 / Packaging and Delivery

### 7a. 模块打包 / Module Packaging

```
module_id/
├── module.prop              # 必需 / required
├── MODULE_NAME.ko           # 必需 / required
├── service.sh               # 必需（加载逻辑）/ required (load logic)
├── post-fs-data.sh          # 可选（早期加载）/ optional (early load)
├── control.sh               # 可选（运行时控制）/ optional (runtime control)
├── profile.conf             # 可选（配置文件）/ optional (config file)
└── skip_mount               # 可选 / optional
```

**module.prop**：
```properties
id=your_module_name
name=Your Module Name
version=1.0.0
versionCode=1
author=YourName
description=Module description
```

**service.sh**（等待依赖，重试加载 / wait for dependencies, retry loading）：
```bash
#!/system/bin/sh
MODDIR=${0%/*}
KMOD="$MODDIR/MODULE_NAME.ko"
MODNAME=module_name

[ -r "$MODDIR/profile.conf" ] && . "$MODDIR/profile.conf"
[ -d "/sys/module/$MODNAME" ] && exit 0
[ -f "$KMOD" ] || exit 1

attempt=0
while [ "$attempt" -lt 90 ]; do
    # 检查依赖模块是否就绪（替换为实际依赖）
    # check if dependency modules are ready (replace with actual dependency)
    if [ -d /sys/module/dependency_module ]; then
        if insmod "$KMOD" enabled=1 observe=0; then
            log -t "$MODNAME" "loaded"
            exit 0
        fi
        log -t "$MODNAME" "insmod failed"
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 1
done
log -t "$MODNAME" "dependencies not ready"
exit 1
```

**注意 / Notes**：
- shell 脚本必须 Unix 换行（LF），权限 0755 / shell scripts must use Unix line endings (LF), permission 0755
- ZIP 条目位于归档根 / ZIP entries at archive root

```bash
cd module_id
zip -r ../MODULE_NAME-KernelSU.zip . -x ".git/*"
sha256sum ../MODULE_NAME-KernelSU.zip
```

### 7b. 交付物 / Deliverables

| 交付物 / Deliverable | 说明 / Description |
|--------|------|
| 模块 zip / module zip | `MODULE_NAME-KernelSU.zip` |
| ko 模块 / ko module | `MODULE_NAME.ko` |
| ko 模块 hash / ko module hash | `sha256sum MODULE_NAME.ko` 的输出 / output |
| 使用说明 / usage docs | 安装方式、参数说明、卸载方式 / install method, params, uninstall |

---

## 绝对禁止 / Absolute Prohibitions

1. 跨设备加载 KO / Load KO on a different device
2. 混用不同 OTA/内核版本的产物 / Mix artifacts from different OTA/kernel versions
3. 跳过静态核对直接 insmod / Skip static verification and insmod directly
4. 跳过 insmod 测试直接打包 / Skip insmod testing and package directly
5. 跳过最终审查直接交付 / Skip final review and deliver directly
6. 盲目照搬 GitHub 项目的偏移/符号名（必须设备验证）/ Blindly copy GitHub offsets/symbol names (must verify on device)
7. 发明 DDIC/DCS 命令 / Invent DDIC/DCS commands
8. 修改 DTBO/boot/vendor_dlkm 分区 / Modify DTBO/boot/vendor_dlkm partitions
9. probe handler 中使用 mutex/kmalloc(GFP_KERNEL)/msleep / Use mutex/kmalloc(GFP_KERNEL)/msleep in probe handlers
10. 不验证原值直接改写内存 / Modify memory without verifying original value
11. 日志不限制频率（回调频率很高）/ Unrestricted logging (callbacks are high-frequency)