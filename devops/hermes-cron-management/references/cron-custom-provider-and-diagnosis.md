# Cron: Custom Providers & Pinned-Model Failure Diagnosis

## 1. Custom provider naming
`config.yaml` `custom_providers:` entries look like:
```yaml
custom_providers:
  - name: agnes
    base_url: https://apihub.agnes-ai.com/v1/chat/completions
    api_key: sk-...
    model: agnes-2.0-flash
    api_mode: chat_completions
```
To target this from a cron job, the `provider` field is the **qualified** form `custom:agnes` (the literal string `custom:` + the YAML `name:`). Bare `custom` is auto-re-mapped to the global provider and fails at run.

### Detection recipe
```bash
# Is a custom provider defined in a profile? which name?
grep -n -A4 "custom_providers:" profiles/default/config.yaml
# Compare default vs research (do they diverge?)
diff <(grep -A6 "custom_providers:" profiles/default/config.yaml) \
     <(grep -A6 "custom_providers:" profiles/research/config.yaml)
```

## 2. Liveness probe (curl, bypasses cron)
Confirms the upstream API is alive before committing a model to a job.
```bash
cd /opt/data
API_KEY=$(grep -A2 "name: agnes" profiles/default/config.yaml | grep api_key | awk '{print $2}')
BASE_URL=$(grep -A2 "name: agnes" profiles/default/config.yaml | grep base_url | awk '{print $2}')
curl -s -o /tmp/resp.txt -w "HTTP_CODE=%{http_code} TIME=%{time_total}s\n" \
  "$BASE_URL" -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"say OK"}]}' --max-time 45
cat /tmp/resp.txt | head -c 600
```
Observed result for agnes (2026-07-11): `HTTP 200`, body `{"choices":[{"message":{"content":"OK"...}}]}` in ~0.76s. So the API was fine; the cron failure was purely the `custom` vs `custom:agnes` naming bug.

## 3. Diagnosing a pinned-model cron failure
`cronjob run` returned `execution_success:false` with an empty job object and NO `agent.log` entry. The failure is at the gateway/scheduler layer.

### Find the active gateway
```bash
ps aux | grep "hermes.*gateway" | grep -v grep
# active = cwd /opt/data, no -p flag (PID 146 in this env)
# zombie  = "-p research", state retrying (telegram token lock) — ignore
```

### Read the real error
```bash
grep -n -i -e "agnes" -e "<job_id>" -e "drift" -e "not supported" \
  /opt/data/logs/gateways/default/current | tail -25
```
Expected signature of the `custom` misnaming bug:
```
🔌 Provider: opencode-zen  Model: agnes-2.0-flash
📝 Error: HTTP 401: Model agnes-2.0-flash is not supported
```

## 4. Two-gateway gotcha
`research` gateway (`-p research`) can be a zombie due to `telegram-bot-token_lock`
("Telegram bot token already in use (PID 146)"). Cron is served by the default
gateway (PID 146). Always diagnose from `/opt/data/logs/gateways/default/current`,
never the `research` gateway log.
