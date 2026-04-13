# Contributing

## Local workflow

```bash
uv sync --group dev
uv run ruff check .
uv run python -m unittest discover -s tests
uv build
```

## Expectations

- Keep examples sanitized. Do not commit real bulb suffixes, addresses, local paths, or account-specific data.
- Keep the public brightness contract at `0-100`.
- Preserve the verified H6006 defaults for demo flows: `power on`, `brightness 100`, `ct 2700`.
- Add or update tests when changing packet builders, parsing, CLI validation, or restore behavior.

## Hardware changes

If a change affects real bulbs, update [docs/HARDWARE_TESTING.md](docs/HARDWARE_TESTING.md) with the manual checks that were run.
