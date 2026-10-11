# Android Kernel LKM (SKILL.md)

Standard Agent Skills definition for developing Android kernel loadable modules (KO/LKM) with kprobe/kretprobe.

Compatible with: **OpenCode**, **Claude Code**, and **Codex** (Agent Skills standard).

## Install

The skill folder contains `references/` and `scripts/` alongside `SKILL.md`. Copy the whole folder,
not just `SKILL.md` — the entry point links to those files, and `scripts/extract-abi.py` is part of
the baseline-extraction step.

Any Agent Skills-compatible tool uses the same layout: put the whole folder under that tool's skills
directory.

| Tool | Skills directory |
|------|------------------|
| OpenCode | `~/.config/opencode/skills/` |
| Claude Code | `~/.claude/skills/` |
| Codex | `$CODEX_HOME/skills/` (defaults to `~/.codex/skills/`) |

### OpenCode

```bash
git clone https://github.com/Yunnijian/android-kernel-lkm \
  ~/.config/opencode/skills/android-kernel-lkm
```

Or copy an existing checkout: `cp -R android-kernel-lkm ~/.config/opencode/skills/`.

### Claude Code

```bash
git clone https://github.com/Yunnijian/android-kernel-lkm \
  ~/.claude/skills/android-kernel-lkm
```

### Codex

```bash
git clone https://github.com/Yunnijian/android-kernel-lkm \
  "${CODEX_HOME:-$HOME/.codex}/skills/android-kernel-lkm"
```

### Verify

The tool should list `android-kernel-lkm` as an available skill after installation. The helper script
can be checked directly:

```bash
python3 <skills-dir>/android-kernel-lkm/scripts/extract-abi.py --help
```

`agents/openai.yaml` sits inside the folder and is read from there; it is optional and Codex-only.

## Usage

The skill triggers when the user mentions: `KO`, `LKM`, `内核模块`, `kernel module`, `kprobe`, `kretprobe`, or `insmod`.

The skill guides the agent through:

- **Phase 0**: Feasibility research (GitHub + device reality)
- **Phase 1**: Requirements gathering
- **Phase 2**: Baseline extraction (vermagic, CRC, kheaders, KCFI)
- **Phase 3**: Symbol discovery
- **Phase 4**: Struct layout discovery
- **Phase 5**: Iterative development (minimal probe → progressive, full static verification + insmod testing per iteration)
- **Phase 6**: Final review (code + requirement fulfillment)
- **Phase 7**: Packaging and delivery (module zip + ko + hash)

## Structure

```
android-kernel-lkm/
├── SKILL.md                        # Skill definition (Chinese + English)
├── agents/
│   └── openai.yaml                 # Codex-specific extension (optional)
├── references/                     # Read on demand
│   ├── abi-provenance.md           # Is the baseline the copy the device runs?
│   ├── kcfi-and-dispatch.md        # KCFI limits, vendor dispatch guards, index shifts
│   └── rollback-and-forensics.md   # Rollback order, crash forensics, log capture
├── scripts/
│   └── extract-abi.py              # Dump vermagic / build id / __versions / __version_ext
└── README.md
```

## License

GPL-2.0
