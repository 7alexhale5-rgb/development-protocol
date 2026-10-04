# Porting rules for bundled skills

Every skill in `skills/` is a standalone port of a skill from a private working setup. A port must
work on a fresh machine with only this repo installed. These rules are the contract.

## Output

- Write `skills/<name>/SKILL.md`. Add `skills/<name>/references/*.md` only when the source keeps
  real depth in reference files that SKILL.md would bloat. Add `skills/<name>/scripts/` only when
  a step truly needs code, and then only Python 3.9+ standard library or POSIX sh, with a unit test
  under `tests/` if the logic is more than a few lines.
- Frontmatter: `name` (the folder name) and `description` (third person, says what it does and
  when to trigger, under 1,024 characters, rich in the phrases a user would actually type).

## Keep the intensity

The source skills are long because each rule came from a real failure. Keep the method, the
phases, the gates, the checklists, the failure modes, the evidence rules and the stop conditions.
Do not summarize a ten-step phase into one line. A port should run close to the source's core
length once private material is removed. When a rule carries a dated lesson ("measured on
2026-08-10: X broke because Y"), keep the lesson and the date, drop any private detail.

## Remove or replace

| Found in source                                                                 | Do this                                                                                                                          |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Paths under a home folder, private script and reference folders, note vaults    | Inline the needed guidance, or drop it                                                                                           |
| House engines (rule injectors, operating ledgers, memory vaults, session hooks) | Replace state with the project's `.devproto/` checklist and plain files in the repo                                              |
| Client, company or colleague names                                              | Remove. Use neutral examples                                                                                                     |
| Personal rules of the author (who sends email, private model routing, budgets)  | Remove, or generalize to "the team's rule"                                                                                       |
| Other private skills                                                            | Point only to bundled skills (list below). Otherwise inline the essential guidance or mark it "if your team has a tool for this" |
| Vendor tools that cost money or need accounts (search APIs, image generators)   | Make optional with a free fallback                                                                                               |
| Model-specific routing                                                          | Say "a stronger model" or "a different model family". Name no private lanes                                                      |

## Bundled skills (safe to reference by slash name)

`/development-protocol`, `/pathway`, `/brainstorm-stack`, `/research-stack`, `/karpathy`,
`/planning-stack`, `/visual-spec`, `/design-stack`, `/devilsadvocate`, `/audit-setup`,
`/build-stack`, `/review-stack`, `/simplify`, `/commit`, `/ship`, `/compound`, `/closeout-stack`,
`/relentless`, `/1pct`, `/icm`

## Wire into the checklist

Each skill states which checklist row it satisfies and how to record it. The checklist tool is
`scripts/devproto.py` inside the `development-protocol` skill folder. Refer to it as:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step <row> --result pass --evidence <file> --verify "<command>"
```

Rows, in order: `pathway`, `brainstorm`, `research`, `spec`, `planning`, `visual-spec`, `design`,
`premortem`, `audit-setup`, `build`, `verify`, `review`, `simplify`, `commit`, `ship`,
`compound`, `closeout`.

| Row         | Skill                         |
| ----------- | ----------------------------- |
| pathway     | `/pathway`                    |
| brainstorm  | `/brainstorm-stack`           |
| research    | `/research-stack`             |
| spec        | `/karpathy spec`              |
| planning    | `/planning-stack`             |
| visual-spec | `/visual-spec`                |
| design      | `/design-stack`               |
| premortem   | `/devilsadvocate --premortem` |
| audit-setup | `/audit-setup`                |
| build       | `/build-stack`                |
| verify      | `/karpathy verify`            |
| review      | `/review-stack`               |
| simplify    | `/simplify`                   |
| commit      | `/commit`                     |
| ship        | `/ship`                       |
| compound    | `/compound`                   |
| closeout    | `/closeout-stack`             |

Name a concrete evidence file (under `.devproto/evidence/` unless the project has its own place)
and a verifier that only reads it. A verifier must not rewrite its own evidence.

## Portability

- Works in Claude Code and Codex. Name tools by what they do ("read the file", "run the tests"),
  and put Claude-Code-only features (subagents, plan mode) behind "if your agent supports it".
- Optional tools (`gh`, a second model's CLI, Playwright, Lighthouse) are marked optional, with
  what to do without them.

## Writing

Plain English. Short sentences. No em dashes. No emojis. Explain a technical word the first time.

## Before you report

1. `bash tests/sanitization.sh skills/<name>` prints `clean`.
2. Every file you wrote is read back once.
3. Report per skill: files written with line counts, source line count, and each thing you
   dropped with the reason.
