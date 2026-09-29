# Compare Mode, Tone and Rules

The tone and the important rules here govern every `--metrics` run, not only compare mode.

## Compare mode

When the user runs `/compound --metrics compare` (or `/compound --metrics compare 14d`):

1. Compute metrics for the current window (default 7d) from the midnight-aligned start date,
   exactly as in the main retro. Example: today is 2026-04-20 and the window is 7d, so use
   `--since="2026-04-13T00:00:00"`.
2. Compute metrics for the prior window of the same length. Use both `--since` and `--until`
   with midnight-aligned dates so the windows do not overlap. Example: for a 7d window starting
   2026-04-13, the prior window is `--since="2026-04-06T00:00:00" --until="2026-04-13T00:00:00"`.
3. Show a side-by-side table with deltas and arrows.
4. Write a short narrative on the biggest improvements and the biggest regressions.
5. Save only the current-window snapshot to `.devproto/retros/`, as a normal run would. Do
   **not** save the prior-window metrics. A saved prior window would be picked up later as if it
   were a real run.

## Tone

- Encouraging but candid. No coddling.
- Specific and concrete. Always anchor in actual commits and code.
- Skip generic praise ("great job!"). Say exactly what was good and why.
- Frame improvements as leveling up, not criticism.
- **Praise should sound like something you would say in a one-on-one**: specific, earned,
  genuine.
- **Growth suggestions should sound like investment advice**: "this is worth your time
  because...", never "you failed at...".
- Never compare teammates against each other negatively. Each person's section stands on its own.
- Aim for about 3,000 to 4,500 words in total, a bit longer when there are team sections.
- Use markdown tables and code blocks for data, prose for narrative.
- Write the narrative into the conversation. Do not write it to a file. The only file written is
  the JSON snapshot (`.devproto/retros/` or `~/.devproto/retros/`).

## Important rules

- All narrative goes to the user in the conversation. The only files written are the JSON
  snapshots.
- Use `origin/$DEFAULT` for every git query, not the local default branch, which may be stale.
- Show every timestamp in the user's local timezone. Do not override `TZ`.
- If the window has zero commits, say so and suggest a different window.
- Round LOC per hour to the nearest 50.
- Treat merge commits as pull request boundaries.
- On the first run (no earlier retros), skip the comparison sections gracefully.
- **Global mode** does not need a git repository. It saves snapshots to `~/.devproto/retros/`,
  not `.devproto/retros/`. It compares only against earlier global retros with the same window.
  If the streak reaches the 365-day cap, show "365+ days".

## Attribution

The `--metrics` mode is adapted from the `/retro` skill in the open-source gstack project
(github.com/garrytan/gstack). Its runtime dependencies (helper scripts, telemetry, proactive
prompts, writing-style layer) were removed. The shipping-streak and test-health logic is kept
unchanged.
