# ABI 来源核对 / ABI Provenance

Phase 2 的前提是「你手上那份 vendor ko 就是设备在跑的那份」。这一步单独列出来，因为它
被跳过时，后面所有静态核对都会通过，然后 insmod 直接崩或静默失效。
The assumption behind Phase 2 is "the vendor ko you hold is the one the device runs". It gets
its own document because skipping it makes every later static check pass and then insmod crashes
or silently does nothing.

## 为什么必须核对 / Why

同一台设备在不同 OTA 上可以带**不同的**厂商框架模块（显示、充电、热控等）：
The same device on different OTAs can ship **different** vendor framework modules (display,
charging, thermal, ...):

- 枚举成员增减 → 函数表里每一项的编号整体位移
  an enum gains/loses a member → every later index in a function table shifts
- 结构体字段增减 → 全部后续偏移变化
  a struct gains/loses a field → every later offset changes
- build id / vermagic 变化 → 根本不能互相加载
  build id / vermagic changes → the two builds cannot even load each other's modules

## 核对步骤 / Steps

```bash
# 1. 设备上真正加载的是哪些模块，路径在哪
#    which modules are actually loaded, and where they live
adb shell cat /proc/modules | head -50      # 或 lsmod
adb shell ls -l /vendor/lib/modules/ | head
adb shell ls -l /lib/modules/ 2>/dev/null

# 2. 有的厂商把模块放在 vendor_boot ramdisk 里，不在 vendor_dlkm；名字先查清楚
#    some vendors keep modules in the vendor_boot ramdisk, not vendor_dlkm; find the real path
adb shell 'ls -l /sys/module/<vendor-module>/ 2>/dev/null; \
            find / -name "<vendor-module>.ko" 2>/dev/null | head'

# 3. 取设备实际加载的那份
#    pull the copy the device actually loads
adb pull /vendor/lib/modules/<module>.ko abi/live-vendor.ko

# 4. 与你准备用来对齐 ABI 的那份比对 build id / vermagic
#    compare build id / vermagic against the copy you were about to build against
llvm-readelf -n abi/live-vendor.ko | grep -i "build id"
llvm-readelf -n abi/<your-reference>.ko | grep -i "build id"
strings -a abi/live-vendor.ko | grep -m1 'vermagic='
strings -a abi/<your-reference>.ko | grep -m1 'vermagic='
```

`build id` 不同 → **不能**用后者反汇编出来的枚举值/偏移去写代码，先拿到设备真身。
Different `build id` → do **not** write code from the latter's disassembled enums/offsets; get
the real one first.

vermagic 不同就更直接：这两个模块在运行时互不兼容，别浪费时间比对偏移。
Different vermagic is even more direct: the two modules are mutually unloadable; stop comparing
offsets and go get the right file.

## 从镜像解包时的额外陷阱 / Extra trap when extracting from images

从 `vendor_boot.img` / `vendor_dlkm.img` 解出来的 ko，可能**不是**当前 ROM 版本：

A ko unpacked from `vendor_boot.img` / `vendor_dlkm.img` may **not** belong to the installed ROM:

```bash
# ko 的 vermagic 与设备 uname -r 不一致 = 这个镜像不是当前系统
# ko vermagic != device uname -r  =>  this image is not the installed system
adb shell uname -r
strings -a extracted/<path>/<vendor-module>.ko | grep -m1 'vermagic='
```

两者不一致时，以 `uname -r` 为准去判断「镜像拿错了」，而不是反过来怀疑设备。
When they disagree, use `uname -r` to conclude "wrong image", not the other way around.

## 让下一次日志自带证据 / Make the next log self-sufficient

在模块的 `post-fs-data.sh` 里把设备在用的 vendor ko 复制一份出来，日志包就会自带 ABI 基准：
Have the module's `post-fs-data.sh` copy the live vendor ko out, so the log bundle carries its own
ABI baseline:

```sh
VENDOR_DIR="$MODDIR/vendor-modules"
mkdir -p "$VENDOR_DIR" 2>/dev/null || return 0
for VENDOR_KO in <vendor-module-a>.ko <vendor-module-b>.ko; do
  [ -f "$VENDOR_DIR/$VENDOR_KO" ] && continue
  for VENDOR_SRC in /vendor/lib/modules /lib/modules /vendor_boot/lib/modules; do
    if [ -f "$VENDOR_SRC/$VENDOR_KO" ]; then
      cp -f "$VENDOR_SRC/$VENDOR_KO" "$VENDOR_DIR/$VENDOR_KO" 2>/dev/null && break
    fi
  done
done
```

同时把厂商驱动自己的打印一起抓进日志（换成对应框架的 tag），否则只有内核 `dmesg` 里
属于自己模块的那几行，看不到厂商侧的 early return 原因。
Also capture the vendor driver's own prints (substitute that framework's tags); otherwise the log
only has your own module's lines and the vendor-side early-return reason is invisible.

```sh
dmesg | grep -E 'your_module|<vendor-framework-tags>' | tail -n 80
```
