# List builds

Companies, people, properties or records gathered from several sources: "every commercial
cleaner in these counties", "the complete list of vendors that do X".

If your team has a list-building method (which providers, which phases, how the list is
delivered), run it for that. This file is about keeping the list honest: a universe that is
re-runnable, a key that dedupes, and a depth that means the record was checked.

## Build the universe so close can re-run it

- The population frame comes from every source that could hold members: licensing boards
  and state filings, directories, map listings, association rosters, the client's own CRM
  export. Each source is one enumeration.
- Save each source's results to files first (one file per record, or one JSONL per source),
  then enumerate the files: `add --from-cmd 'ls records/*.json'`. A live API query cannot
  be re-run at `close` and give the same answer. Files can.
- Pick the id before you add anything: a normalized key such as the domain for a company, a
  license number, or `name|city` in lower case. Dedupe on it before visiting, and merge
  records that share it.

## Traps

- **Silent caps.** Map searches and most APIs cap how many results one query returns,
  without saying so. Split the query by geography or category until every piece comes back
  under the cap, and record each split as its own enumeration.
- **Metered vendors.** Paid data providers bill per call. Preview a small sample before the
  full pull, check the balance on the vendor's own usage page rather than trusting a
  formula, and never start a paid call with no credits left. Free sources (public
  registries, the client's export) come first.
- **Near-duplicates.** Chains and franchises, PO boxes, a business listed under its owner's
  name, the same company in two sources with different spellings.
- **Criteria buried in prose.** When membership depends on a fact ("offers emergency
  service", "serves this county"), the fact is often phrased many ways and sits far down the
  page. That is why the floor is a full read, not a keyword hit.

## What the depths mean here

- L1: a name in a listing.
- L2: the record verified from its own source page. The fields are filled, and the evidence
  carries the source URL or file and the line that settles membership.
- L3: cross-checked in a second, independent source.
- L4: a live check, such as the site resolving or the phone number being in service. Never
  contact anyone to verify: outbound messages are the user's to send, not the agent's.

## Done conditions

- "Every business in the frame from sources A, B and C listed, deduped on domain, and
  verified at L2; dead source pages deferred with the reason."

## Pairs with

`/research-stack` for finding the sources that make up the frame.
