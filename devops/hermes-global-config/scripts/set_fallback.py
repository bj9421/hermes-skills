#!/usr/bin/env python3
"""
set_fallback.py — Safely set fallback_providers in config.yaml.

Uses this when `hermes config set fallback_providers.0.xxx` fails with
IndexError because the list is empty.

Usage:
  python3 set_fallback.py <config_path> <provider> <model> [index]

Examples:
  python3 set_fallback.py /opt/data/config.yaml opencode big-pickle
  python3 set_fallback.py /opt/data/config.yaml custom:agnes agnes-2.0-flash 1
  python3 set_fallback.py /opt/data/profiles/research/config.yaml custom:agnes agnes-2.0-flash
"""

import sys
import yaml

def main():
    if len(sys.argv) < 4:
        print("Usage: set_fallback.py <config_path> <provider> <model> [index]")
        sys.exit(1)

    config_path = sys.argv[1]
    provider = sys.argv[2]
    model = sys.argv[3]
    index = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Ensure fallback_providers exists
    if 'fallback_providers' not in config or not config['fallback_providers']:
        config['fallback_providers'] = []

    # Pad list if needed
    while len(config['fallback_providers']) <= index:
        config['fallback_providers'].append({})

    config['fallback_providers'][index]['provider'] = provider
    config['fallback_providers'][index]['model'] = model

    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"✓ Set fallback[{index}]: provider={provider}, model={model}")
    print(f"  Config: {config_path}")
    print(f"  All fallbacks: {config['fallback_providers']}")

if __name__ == '__main__':
    main()
