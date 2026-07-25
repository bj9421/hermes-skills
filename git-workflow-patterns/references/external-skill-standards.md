# External Skill Registries & Standards

## agentskills.io — Agent Skills Specification

**Not a marketplace.** This is an open standard defining the `SKILL.md` format so different AI agents can consume skills uniformly.

- **Spec**: https://agentskills.io/specification.md
- **Docs index**: https://agentskills.io/llms.txt
- **Supported clients**: Hermes Agent, Gemini CLI, Junie (JetBrains), Autohand Code CLI, etc.
- **No search/install API yet** — it's a spec, not a registry.

### SKILL.md Format Requirements

| Field | Required | Constraints |
|-------|----------|-------------|
| `name` | Yes | Max 64 chars, lowercase + hyphens only, no leading/trailing hyphen |
| `description` | Yes | Max 1024 chars, describes what skill does and when to use it |
| `license` | No | License name or reference to bundled file |
| `compatibility` | No | Max 500 chars, environment requirements |
| `metadata` | No | Arbitrary key-value mapping |
| `allowed-tools` | No | Space-separated pre-approved tools (experimental) |

### Directory Structure

```
skill-name/
├── SKILL.md          # Required
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files
```

### Future Outlook

A skill registry/marketplace may be added later. Watch for announcements on the [agentskills Discord](https://discord.gg/MKPE9g8aUy).
