# MCP Server Installation in Container/Restricted Environments

Installing MCP servers (e.g., `duckduckgo-mcp-server`) via `uvx` or `uv tool install` in a Docker container where `/root` is inaccessible requires workarounds.

## Root Problem

The `hermes` user in Docker doesn't have permission to write to `/root/.cache/uv`, `/root/.local/share/uv/`, or `/root/.local/bin/`. `uv` defaults to these paths and fails with `Permission denied`.

## Workaround: Install via uv with Custom Dirs

```bash
# Set writable paths under /opt/data (or another writable volume)
export UV_CACHE_DIR=/opt/data/.cache/uv
export UV_TOOL_DIR=/opt/data/.local/share/uv/tools
export UV_PYTHON_INSTALL_DIR=/opt/data/.local/share/uv/python

mkdir -p "$UV_CACHE_DIR" "$UV_TOOL_DIR" "$UV_PYTHON_INSTALL_DIR"

uv tool install duckduckgo-mcp-server
```

The package installs into `$UV_TOOL_DIR/duckduckgo-mcp-server/` but `uv tool install` may still fail at the last step trying to create `/root/.local/bin/` for the symlink. The package **is already installed** — just the symlink step fails.

## Run Directly from Tool Venv

Since the executable symlink can't be created in `/root/.local/bin/`, run the server directly from its tool venv Python:

```bash
# Find the tool venv python
ls /opt/data/.local/share/uv/tools/duckduckgo-mcp-server/bin/python3

# Check entry point (from dist-info/entry_points.txt):
# duckduckgo-mcp-server = duckduckgo_mcp_server.server:main
# So the module is: duckduckgo_mcp_server.server

# Test that it starts:
/opt/data/.local/share/uv/tools/duckduckgo-mcp-server/bin/python3 \
  -m duckduckgo_mcp_server.server
# Expected output:
# DuckDuckGo MCP Server initialized:
#   SafeSearch: MODERATE (kp=-1)
#   Default Region: none
#   Search backend: auto
```

## Register with Hermes via `hermes mcp add`

Use the full venv Python path as the command:

```bash
hermes mcp add duckduckgo \
  --command /opt/data/.local/share/uv/tools/duckduckgo-mcp-server/bin/python3 \
  --args -m duckduckgo_mcp_server.server
```

### CRITICAL: `--args` Must Be Last

The `--args` flag takes `...` (variable number of arguments) and **must be the last option** before the positional `name` argument. This is a Click/argparse limitation — everything after `--args` is consumed as arguments until another flag or the positional arg.

✅ Correct:
```bash
hermes mcp add duckduckgo \
  --command /path/to/python3 \
  --args -m duckduckgo_mcp_server.server
```

❌ Wrong — `--args` not last:
```bash
hermes mcp add --command /path/to/python3 --args -m duckduckgo_mcp_server.server duckduckgo
```

## YAML List Config Pitfall

`hermes config set mcp_servers.X.args '["-m", "module"]'` stores the value as a **YAML string** (quoted scalar), not a proper YAML list. This causes `hermes mcp test` to fail:

```
1 validation error for StdioServerParameters
args
  Input should be a valid list [type=list_type, input_value='["-m", "module"]', input_type=str]
```

**Only `hermes mcp add --args` produces the correct YAML list format:**

```yaml
mcp_servers:
  duckduckgo:
    command: /path/to/python3
    args:
      - -m
      - duckduckgo_mcp_server.server    # ✅ proper YAML list
```

If you accidentally wrote a string value with `hermes config set`, remove it first (`hermes config set mcp_servers.X.args ''` or `hermes mcp remove X`) then re-add with `hermes mcp add --args`.

## Verify

```bash
# List configured servers
hermes mcp list

# Test connection
hermes mcp test duckduckgo

# Expected: ✓ Connected
```

## Alternative: Full Hermes Config Section

If `hermes mcp add` is unavailable or behaves unexpectedly, the config section can be written manually (but ensure correct YAML list syntax):

```yaml
mcp_servers:
  duckduckgo:
    command: /opt/data/.local/share/uv/tools/duckduckgo-mcp-server/bin/python3
    args:
      - -m
      - duckduckgo_mcp_server.server
```

Then restart Hermes for it to pick up the new server.

## Summary

| Step | Command |
|------|---------|
| Install | `uv tool install` with UV_TOOL_DIR/UV_CACHE_DIR set |
| Run | Tool venv `python3 -m module.server` |
| Register | `hermes mcp add NAME --command PATH --args ...` |
| Args pitfall | `--args` must be LAST option; never use `hermes config set` for list values |
