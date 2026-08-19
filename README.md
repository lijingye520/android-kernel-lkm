# Android Kernel LKM (SKILL.md)

Standard Agent Skills definition for developing Android kernel loadable modules (KO/LKM) with kprobe/kretprobe.

Compatible with: **OpenCode**, **Claude Code**, and **Codex** (Agent Skills standard).

## Install

### OpenCode

```bash
# Copy to global skills directory
mkdir -p ~/.config/opencode/skills/android-kernel-lkm
cp SKILL.md ~/.config/opencode/skills/android-kernel-lkm/SKILL.md
```

### Claude Code

```bash
mkdir -p ~/.claude/skills/android-kernel-lkm
cp SKILL.md ~/.claude/skills/android-kernel-lkm/SKILL.md
```

### Codex

```bash
mkdir -p ~/.codex/skills/android-kernel-lkm
cp SKILL.md ~/.codex/skills/android-kernel-lkm/SKILL.md
mkdir -p ~/.codex/skills/android-kernel-lkm/agents
cp agents/openai.yaml ~/.codex/skills/android-kernel-lkm/agents/openai.yaml
```

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
├── SKILL.md               # Skill definition (Chinese + English)
├── agents/
│   └── openai.yaml        # Codex-specific extension (optional)
└── README.md
```

## License

GPL-2.0
