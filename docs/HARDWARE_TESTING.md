# Hardware Testing

## Default baseline

Use this baseline before and after demo-style tests:

- `power=True`
- `brightness=100`
- `ct=2700`

## Manual checklist

- `uv run h6006ctl scan`
- `uv run h6006ctl status`
- `uv run h6006ctl on`
- `uv run h6006ctl off <target>`
- verify `off` visually on the bulb itself; do not rely on an immediate fresh-session status query after power-off
- `uv run h6006ctl brightness 1 <target>`
- `uv run h6006ctl brightness 50 <target>`
- `uv run h6006ctl brightness 100 <target>`
- `uv run h6006ctl rgb 255 0 0 <target>`
- `uv run h6006ctl rgb 0 255 0 <target>`
- `uv run h6006ctl rgb 0 0 255 <target>`
- `uv run h6006ctl ct 2700 <target>`
- `uv run h6006ctl ct 4000 <target>`
- `uv run h6006ctl ct 6500 <target>`
- verify one-bulb targeting by suffix placeholder such as `ABCD`
- verify all-bulb targeting with no explicit target
- interrupt a command and verify the next command still succeeds
- `uv run h6006ctl identify <target>` and confirm it restores the default baseline
- `uv run h6006ctl funny` and confirm it restores the default baseline

## Release acceptance

Before publishing or tagging a release:

- `uv run ruff check .`
- `uv run python -m unittest discover -s tests`
- `uv build`
- manual checklist completed on real H6006 bulbs

## Observed quirk

On the tested H6006 bulbs, a power-off command can be confirmed in the same BLE session, but a brand-new reconnect/query after power-off may read back as `power=True` again. Treat `off` as visually verified behavior rather than a strong fresh-session status invariant.
