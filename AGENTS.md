# Working on BrokerBridge

- Keep external adapters read-only until a separate, explicitly authorized execution milestone.
- Do not add an environment switch that bypasses the absence of live execution.
- Preserve currency, broker, account, environment and synthetic-data labels. Do not fabricate NAV.
- Never commit credentials, `.env`, local state, account snapshots, or confirmation tokens.
- Update public tool descriptions and docs when behavior or scope changes.
- Before handoff run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`,
  and `uv build`. Add meaningful tests for order state, idempotency, policy and broker mappings.
- Verify time-sensitive financial/regulatory claims against dated primary sources. Keep
  compliance plans distinct from implemented enforcement.
