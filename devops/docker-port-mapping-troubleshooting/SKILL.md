---
name: docker-port-mapping-troubleshooting
description: Troubleshoot and fix Docker container port mapping issues for services running in Hermes Agent containers (e.g., dashboard, gateways).
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [docker, port, mapping, troubleshooting, dashboard, gateway]
---

# Docker Port Mapping Troubleshooting for Hermes Agent

## When to use this skill

Use this skill when:
- A service running inside a Hermes Agent container (e.g., the dashboard, a profile gateway) is not accessible from the host machine or other devices on the network.
- You suspect the container's ports are not properly mapped to the host.
- You need to verify or adjust port mapping for a Hermes container running in Docker.

This skill focuses on the Docker `port` command and `docker run -p` syntax. It does not cover service internal configuration (e.g., why a gateway fails to start) — see `hermes-s6-container-supervision` for supervision-related issues.

## Quick recipes

### 1. Check current port mapping for a running container

```bash
# Replace <container> with the container name or ID (e.g., hermes)
docker port <container>
```

Example output:
```
9119/tcp -> 0.0.0.0:8501
8501/tcp -> 127.0.0.1:8501
```

This shows:
- Container port 9119 is mapped to host port 8501 on all interfaces (0.0.0.0) and also to localhost only (127.0.0.1) — the first mapping is the one that matters for external access.
- If you see nothing or only `->` without a host port, the port is not mapped.

### 2. Test connectivity to the mapped host port

From the host machine (or another device on the same network):
```bash
# Replace <host_ip> with the Docker host's IP (often the Raspberry Pi's LAN IP)
# Replace <host_port> with the port from the docker port output (e.g., 8501)
curl -s http://<host_ip>:<host_port> || echo "Connection failed"
```

Or use a browser: `http://<host_ip>:<host_port>`

### 3. Restart container with correct port mapping

Stop the container first:
```bash
docker stop <container>
```

Then restart with the desired mapping. For the Hermes dashboard (default internal port 9119):
```bash
docker run -d \
  --name <container> \
  -p <host_port>:9119 \   # e.g., -p 8501:9119 to access via host port 8501
  -v /opt/data:/opt/data \
  -v /root/.hermes:/root/.hermes \
  hermes:latest   # adjust image name/tag as needed
```

> **Note**: Always include your existing volume mounts (`-v`) and other necessary flags. Use `docker inspect <container>` to see the original `run` command if unsure.

### 4. Verify the dashboard is binding to 0.0.0.0 inside the container

If you suspect the service is bound to localhost only (which would prevent external access even with port mapping), check the service configuration:
- For the dashboard: look for `HERMES_DASHBOARD_HOST` in the container environment or in the service run script.
- The default is `0.0.0.0` (all interfaces). If set to `127.0.0.1`, change it to `0.0.0.0` or unset it.

## Common pitfalls

### Pitfall: Assuming the container's internal port is the same as the host port
- Many Hermes services (like the dashboard) listen on specific ports by default but can be configured via environment variables.
- The dashboard inside the container listens on port 9119 by default, but this can be changed via the `HERMES_DASHBOARD_PORT` environment variable.
- Mapping `-p 8501:8501` would try to map host port 8501 to container port 8501 — but nothing is listening on 8501 inside the container unless `HERMES_DASHBOARD_PORT=8501` is set.
- **Fix**: Either:
  1. Map host port to the container's actual listening port (e.g., `-p 8501:9119` for default dashboard port), OR
  2. Set the service to listen on the container port you want to map (e.g., `-e HERMES_DASHBOARD_PORT=8501` and `-p 8501:8501`).

### Pitfall: Forgetting to restart the container after changing port mapping
- Port mapping is set at container creation and cannot be changed on a running container.
- **Fix**: Stop the container, then run `docker run` again with the corrected `-p` flag.

### Pitfall: Confusing `docker port` output with actual accessibility
- `docker port` only shows the mapping configured by Docker. It does not test if the service is actually listening or if firewalls block access.
- **Fix**: After verifying mapping, test with `curl` or a browser as shown above.

### Pitfall: Using `localhost` or `127.0.0.1` from another device
- The Docker host's `localhost` is not accessible from other devices on the network.
- **Fix**: Use the host's LAN IP (e.g., `192.168.x.x` or `10.x.x.x`) obtained via `hostname -I` on the Raspberry Pi.

### Pitfall: Container UID mismatch breaks cross-container file access
- Multiple containers on the same host share bind-mounted directories (e.g., `/home/hermes_data/` mounted into both Hermes and Syncthing containers).
- **Problem:** If containers run under different UIDs (e.g., Hermes=10000, Syncthing=1000), the lower-UID container cannot read/write files created by the higher-UID container.
- **Symptom:** Syncthing shows "Local Additions" or "REVERT LOCAL CHANGES" because it cannot access newly created files; new files remain invisible to other containers.
- **Fix:** Ensure all containers sharing the same bind mount use the **same PUID/PGID**. In Portainer, edit the container's Environment Variables and set `PUID` and `PGID` to match the host user that owns the files. Then redeploy the container.
- **Verification:** After fixing, create a test file and confirm it appears in the other container's view or on the mobile Syncthing app.
- **2026-07-09 lesson:** UID 1000 vs 10000 mismatch caused 3 days of sync failures. Always check `id <username>` and container PUID settings when cross-container file access fails.

### Pitfall: Directory permissions block cross-container access
- Even with matching UIDs, if the shared directory has mode `700`, only the owner can traverse it.
- **Fix:** `chmod 755 <shared_dir>` or `chmod -R a+rX <shared_dir>` for directories containing files that need to be readable by other containers.
- **Best practice:** Set `umask 0022` in the container that creates files, so new files are world-readable by default.

### Pitfall: New files created with 600 permissions block cross-container read
- Some containers (like Hermes) create files with mode `600` (owner-only read/write).
- Even with matching UIDs, if the file is `600`, other containers running as different users can't read it.
- **Fix:** `chmod 644 <file>` or `chmod -R a+rX <directory>` after creating files.
- **Better fix:** Set `umask 0022` in the container's entrypoint so new files default to `644`.

### Pitfall: Container DNS is isolated from host — host DNS changes don't propagate

Docker bridge-network containers have their own network namespace. Changes to host DNS (`/etc/resolv.conf`, `/etc/docker/daemon.json`) do NOT automatically apply to running containers.

**Symptoms:**
- Host DNS changed to faster server, but container still uses old DNS
- `cat /etc/resolv.conf` inside container shows stale nameserver
- Container resolv.conf says "Based on host file" but still has old values

**Why:** Docker copies host resolv.conf into the container at creation time. The container's resolv.conf becomes static after that — even `docker restart` doesn't re-copy it. Only `docker stop && docker rm && docker run` (rebuild) refreshes it.

**Fix hierarchy:**
1. **`/etc/docker/daemon.json`** — add `"dns": ["168.95.192.1", "8.8.8.8"]` + `sudo systemctl restart docker` → affects NEW containers only
2. **`docker-compose.yml`** — add `dns: [168.95.192.1, 8.8.8.8]` + rebuild → affects that compose stack
3. **Rebuild container** — only way to apply to an existing running container

**2026-07-23 lesson:** Telegram connection instability partially caused by slow DNS (100.100.100.100 at 24ms). Fixed by changing daemon.json DNS to 168.95.192.1 (9ms) + container rebuild.

### Pitfall: Host sysctl changes don't propagate to bridge-network containers

TCP keep-alive and other kernel parameters set via `sysctl -w` on the host do NOT apply inside Docker bridge-network containers. Each container has its own network namespace with its own sysctl values.

**Symptoms:**
- `cat /proc/sys/net/ipv4/tcp_keepalive_time` inside container shows 7200 (default) even after host sysctl changed to 60
- Telegram/HTTP connections drop after long idle periods despite host keep-alive being configured

**Fix options (pick one):**
1. **Rebuild container with `--sysctl`:**
   ```bash
   docker stop hermes && docker rm hermes
   docker run -d --name hermes \
     --sysctl net.ipv4.tcp_keepalive_time=60 \
     --sysctl net.ipv4.tcp_keepalive_intvl=10 \
     --sysctl net.ipv4.tcp_keepalive_probes=5 \
     ... (rest of original docker run flags)
   ```
2. **docker-compose.yml:** Add `sysctls:` section under the service
3. **Skip** — rely on application-level reconnection (gateway auto-reconnect)

**2026-07-23 lesson:** User declined container rebuild due to data safety concern. Host sysctl was set for persistence but doesn't affect the container. Gateway's built-in auto-reconnect is the fallback.

### Pitfall: Syncthing syncs `.git/` causing conflicts
- When vault has both Syncthing and GitHub, `.git/` directory gets synced to mobile.
- **Symptom:** Mobile Syncthing shows "1 conflicts" with `.git/` files.
- **Fix:** Add `.git/` and `.git` to `.stignore` in the vault root.
- **See also:** `references/obsidian-vault-github-sync.md`

## Related skills

- `hermes-s6-container-supervision`: For diagnosing why a supervised service (like the dashboard) isn't starting or crashing.
- `hermes-agent`: For general Hermes Agent configuration, including dashboard-related settings in `config.yaml`.
- `webhook-subscriptions`: If troubleshooting webhook delivery (different issue, but also involves network accessibility).
- `uid-mismatch-debugging` (reference): Detailed debugging workflow for cross-container UID/GID permission issues.

## Supporting files

- `references/obsidian-vault-github-sync.md` — Obsidian vault GitHub sync setup and daily backup script
- `scripts/github_backup.sh` — Automated daily backup script (cron-ready)

## Verification steps

After applying a fix:
1. Run `docker port <container>` to confirm the mapping.
2. Use `curl` or a browser from another device on the same network to access `http://<host_ip>:<host_port>`.
3. Check the container logs for service startup errors: `docker logs <container>`.

## Example: Fixing inaccessible dashboard

Symptoms: Dashboard configured (`HERMES_DASHBOARD=1`) but `http://<pi_ip>:8501` times out or refuses connection.

Steps:
1. `docker port hermes` → shows no mapping for 9119/tcp.
2. Stop container: `docker stop hermes`.
3. Restart with mapping:  
   `docker run -d --name hermes -p 8501:9119 -v /opt/data:/opt/data -v /root/.hermes:/root/.hermes hermes:latest`
4. Verify: `docker port hermes` → `9119/tcp -> 0.0.0.0:8501`.
5. Access from browser: `http://<pi_ip>:8501`.
