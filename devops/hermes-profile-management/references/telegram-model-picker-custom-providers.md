# Telegram Model Picker — Custom Providers

## Finding the picker code

The Telegram gateway's inline keyboard model picker is in:
- `/opt/hermes/plugins/platforms/telegram/adapter.py` — `send_model_picker()` (line ~4406)
- `/opt/hermes/hermes_cli/model_switch.py` — `list_picker_providers()` (line ~2311)
- `/opt/hermes/hermes_cli/models.py` — `group_providers()` (line ~1129)

## How custom providers appear

`list_picker_providers()` receives `custom_providers` as a parameter and includes them in the returned list. The Telegram adapter then passes this list to `group_providers()` which folds provider families (Kimi, xAI, etc.) into submenus.

**Custom providers are NOT grouped** — they appear as single buttons (e.g., `custom:agnes`). They are visible in the picker as long as:
1. They are defined under `custom_providers` in the active `config.yaml`
2. The gateway has successfully loaded the config (not stuck in a retry loop)

## Troubleshooting: custom provider missing from Telegram picker

If a custom provider (e.g., `custom:agnes`) does not appear in the Telegram model picker:

1. **Verify it's in the config**: `grep -A5 "name: agnes" /opt/data/config.yaml`
2. **Check the gateway loaded it**: `grep "custom:agnes" /opt/data/logs/gateways/default/current`
3. **Test locally**: Run the same `list_picker_providers()` call with the config — if it returns `custom:agnes`, the picker should show it.
4. **Restart the gateway**: If the config changed after the gateway started, restart it.
5. **Check for token conflicts**: If another gateway owns the Telegram token, the picker may not update.

## Known behavior

- `custom:agnes` slug is generated from the `name:` field in `custom_providers` YAML block
- The provider group `group_providers()` does NOT fold custom providers into any group — they always appear as singles
- If the custom provider's API key is missing or invalid, it still appears in the picker but model selection will fail at runtime