#!/bin/bash
# GitHub backup cron job
# Pushes obsidian-vault to GitHub daily
# Usage: crontab -e → 0 22 * * * /opt/data/scripts/github_backup.sh

cd /opt/data/obsidian-vault

# Exit if no changes
git diff --quiet HEAD && exit 0

# Commit and push
git add -A
git commit -m "Auto backup: $(date '+%Y-%m-%d %H:%M')"
git push 2>&1

echo "Backup completed at $(date '+%Y-%m-%d %H:%M')"
