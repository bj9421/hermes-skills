#!/bin/bash
# propagate_api_keys.sh
# Copies API keys from a source profile to target profiles (or global .env if allowed)
# Usage: ./propagate_api_keys.sh <source_profile> [target1 target2 ...]
# If no targets given, defaults to global .env, default profile, coder profile

set -euo pipefail

SOURCE_PROFILE="${1:-research}"
shift || true

# Default targets: global .env, default profile, coder profile
if [ $# -eq 0 ]; then
    TARGETS=(
        "/opt/data/.env"
        "/opt/data/profiles/default/.env"
        "/opt/data/profiles/coder/.env"
    )
else
    TARGETS=("$@")
fi

SOURCE_ENV="/opt/data/profiles/${SOURCE_PROFILE}/.env"

if [ ! -f "$SOURCE_ENV" ]; then
    echo "Error: Source environment file not found: $SOURCE_ENV"
    exit 1
fi

# Extract non-commented API key lines
KEY_LINES=$(grep -v '^#' "$SOURCE_ENV" | grep '_API_KEY=') || true

if [ -z "$KEY_LINES" ]; then
    echo "No API key lines found in $SOURCE_ENV"
    exit 0
fi

echo "Found API key lines:"
echo "$KEY_LINES"

for target in "${TARGETS[@]}"; do
    echo "Processing target: $target"
    # Ensure file exists
    mkdir -p "$(dirname "$target")"
    touch "$target"
    
    # Append each key if not already present
    while IFS= read -r line; do
        if ! grep -qxF "$line" "$target"; then
            echo "Adding: $line"
            echo "$line" >> "$target"
        else
            echo "Already present: $line"
        fi
    done <<< "$KEY_LINES"
done

echo "Done."