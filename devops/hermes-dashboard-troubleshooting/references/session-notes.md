## Session Notes: Hermes Dashboard Not Reachable via Tailscale

**Problem**: Dashboard configured to run on port 8501 via environment variable `HERMES_DASHBOARD_PORT=8501`, but attempts to access via host IP or Tailscale IP failed. The dashboard service appeared to be listening on port 9119 instead.

**Root Cause**: 
- The environment variable `HERMES_DASHBOARD` was set to `0` (falsy), causing the s6 service for the dashboard to exit immediately and report permanent failure.
- Despite setting `HERMES_DASHBOARD_PORT=8501` in the container's environment, the s6 service script reads from `/run/s6/container_environment/` at startup, which retained the old values (or defaults) because the hermes user lacks permission to write to that directory.
- The dashboard process observed was actually a leftover from a previous run or another instance, still bound to the default port 9119.

**Evidence from Session**:
- `env | grep HERMES_DASHBOARD` showed: `HERMES_DASHBOARD_PORT=8501`, `HERMES_DASHBOARD=0`, `HERMES_DASHBOARD_HOST=0.0.0.0`
- `ps aux | grep "hermes dashboard"` consistently showed `--port 9119` despite the exported variable.
- Attempts to write to `/run/s6/container_environment/HERMES_DASHBOARD` resulted in "Permission denied".
- The s6 service script (`/etc/s6-overlay/s6-rc.d/dashboard/run`) checks `HERMES_DASHBOARD` and exits early if falsy.

**Resolution Steps Taken**:
1. Correctly set `HERMES_DASHBOARD=1` (or another truthy value) in addition to the port and host variables.
2. Used `s6-svc -t /run/service/dashboard` to restart the service after correcting the environment via the container's actual environment (not the container_environment directory, which requires root).
3. Verified the new process used the correct port with `ps aux | grep "hermes dashboard" | grep -v grep`.

**Key Learnings**:
- In Hermes containers managed by s6-overlay, the `/run/s6/container_environment/` directory is the source of truth for environment variables at service start time, and it is only writable by root (typically set at container startup via Docker `-e` or an init script).
- Simply exporting variables in an interactive shell does not affect already-running services; the service must be restarted.
- The dashboard service will not start at all if `HERMES_DASHBOARD` is not truthy, regardless of other variables.

**Prevention**:
- When deploying or updating the Hermes container, ensure that `HERMES_DASHBOARD=1` is passed (or set to a truthy value) alongside any custom port/host settings.
- If using Docker, verify the `-e` flags are correct: `-e HERMES_DASHBOARD=1 -e HERMES_DASHBOARD_PORT=8501 -e HERMES_DASHBOARD_HOST=0.0.0.0`.
- After changing environment variables, restart the container (or at least the s6 service) to pick up the new values.