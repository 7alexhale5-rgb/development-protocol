# Migrations

Every reference to an old thing, changed until none remain: renaming an API, moving off a
library, retiring a config key.

## Build the universe from every form of the name

- Code: `rg -n --no-heading 'old_api' -g '!**/vendor/**'`, with ids as `path:line`.
- The name's other forms, each as its own enumeration: config keys, environment variables,
  SQL, docs and examples, strings built at runtime.
- Consumers in other repositories. Enumerate each repo separately and say in the goal which
  repos are in scope.

## The end state is a command

A migration has an unambiguous finish line, so give it to `close`:

`--done-cmd '! rg -q "old_api" src/ && <the test command>'`

Line numbers move as you edit, so enumerate again after each batch of changes. `close`
re-runs the stored enumeration and refuses if new hits appear.

## Traps

- **Generated code** that is regenerated from an old template brings the old name back.
  Migrate the template.
- **Lockfiles and pinned versions** keep the old dependency alive after the code moves.
- **Both paths live.** Feature flags and shims that keep old and new running together need
  their own item, with a date to remove them.
- **Other repos** that import the old name break silently until their next build.

## What the depths mean here

- L2: the call site read.
- L3: its data flow and tests traced.
- L4: migrated, and its test run and passing. Evidence is the test command and its result.

Migrations default to an L4 floor for code and L2 for docs.

## Pairs with

`/build-stack` for making the edits; `/review-stack` before the change ships.
