# Cron Job Migration Checklist

Step-by-step procedure for migrating cron jobs between Hermes profiles.

## Pre-Migration

- [ ] Run `hermes cron list` and note all job IDs to move
- [ ] For each job, note: `name`, `schedule`, `script`, `workdir`, `no_agent`
- [ ] Verify all referenced scripts exist at absolute paths
- [ ] Check if target profile has the same `deliver` target (Telegram chat)

## Migration Steps

1. **Copy scripts to target profile**
   ```bash
   mkdir -p /opt/data/profiles/<target>/scripts
   cp /opt/data/profiles/<source>/scripts/*.sh /opt/data/profiles/<target>/scripts/
   cp /opt/data/profiles/<source>/scripts/*.py /opt/data/profiles/<target>/scripts/
   ```

2. **Update workdir via cronjob**
   ```bash
   hermes cron update <job_id> --workdir /opt/data/profiles/<target>
   ```

3. **Test manually from new workdir**
   ```bash
   cd /opt/data/profiles/<target>
   bash scripts/<script_name>
   ```

4. **Pause source job**
   ```bash
   hermes cron pause <job_id>
   ```

## Post-Migration Verification

- [ ] New workdir job runs at scheduled time
- [ ] Old workdir job does NOT run (paused)
- [ ] Output goes to correct chat
- [ ] No duplicate notifications
