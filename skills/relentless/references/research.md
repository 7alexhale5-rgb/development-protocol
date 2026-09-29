# Research sweeps

Sources on a topic, gathered until more searching stops finding anything new: prior art,
competitor scans, "what has been written about X".

## Build the universe from several routes

- Use at least three independent routes: two or more search engines, citation chasing (what
  the best sources cite, and what cites them), vendor documentation, forums and issue
  trackers, code repositories.
- Log each query as its own enumeration. Save its results to a file, then
  `add --from-file results/<query>.txt`, so the universe records how it was built.
- Ids are canonical URLs (tracking parameters stripped) or DOIs. Syndicated and mirrored
  copies collapse to one id.

## When the universe is closed

Research has no natural edge, so set one you can check: the universe is closed when three
new queries in a row, each phrased differently, add no new relevant source. Record those
three queries as a finding. That finding is the done condition's evidence.

## Traps

- **Paywalls.** Look for a preprint or the author's copy. Otherwise defer with the reason.
- **One source saying it once.** A claim that rests on a single secondary source needs L3
  before it carries a conclusion.
- **Recency without primacy.** The newest article is not the best source unless it is the
  primary one.
- **SEO copies.** Rewritten versions of the same press release are one source.

## What the depths mean here

- L1: a snippet or an abstract.
- L2: the full source read. Evidence quotes the passage that matters.
- L3: traced to the primary source (the paper, filing, dataset or commit) and checked there.
- L4: the number reproduced, or the claim checked against live data.

## Done conditions

- "Sources from routes A, B and C to saturation (three consecutive empty queries, recorded),
  each read at L2, and every load-bearing claim traced to its primary at L3."

## Pairs with

`/research-stack` for gathering and synthesis. This keeps the count of what was actually
read.
