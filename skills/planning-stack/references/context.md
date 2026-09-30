# Context gathering: modes, tools, sources, prior plans

Read by Steps 0, 0.5, 1 and 2 of `SKILL.md`.

## Contents

- Mode auto-detection (Step 0)
- Reusing a prior plan (Step 0.5)
- Tool detection (Step 1)
- The five sources (Step 2)
- Degradation

---

## Mode auto-detection

If neither `--tech` nor `--feature` is given, classify by keyword.

**TECH triggers** (any match): architecture, system design, API, schema, migration, database,
performance, scaling, infrastructure, deployment, CI/CD, security audit, refactor (system-wide),
data flow, microservice, monolith, caching strategy, load balancing.

**FEATURE triggers** (any match): feature, component, page, endpoint, UI, button, form,
workflow, user story, add, implement, build, create (a specific thing), fix, update (a specific
behaviour), notification, dashboard, modal, sidebar.

**Ambiguous** (both match, or neither): ask the user. If your agent has a multiple-choice
question tool, use it:

```text
question: "This goal could be planned as a technical architecture plan or a feature
           implementation plan. Which fits better?"
options:
  - "Technical (--tech)": architecture decisions, system design, data flow, API contracts,
    performance considerations
  - "Feature (--feature)": user stories, file changes, implementation steps, test plan,
    rollback strategy
```

---

## Reusing a prior plan

Search the repository for earlier plans and decisions on the same goal:

```bash
goal_keyword="<goal keyword>"                  # fill in before running
# plans and decisions this skill wrote earlier, plus common project locations
grep -rli "$goal_keyword" .devproto/plans .devproto/decisions .planning docs/adr* \
  docs/architecture* ROADMAP.md 2>/dev/null
```

Check each hit's date (front matter `date:` or the file name). Then:

| Age of the matching plan | Action                                                                                                                                                                 |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Under 24 hours**       | **Fresh hit.** Show the plan with the note "Found a plan from <date>, less than a day old. Showing it." Enter Advisor Mode (Step 7).                                   |
| **1 to 7 days**          | **Stale but usable.** Show it with "Found a plan from <date>, <N> days ago." Ask: "Refresh this plan or use it as is?" Refresh goes to Step 1. Otherwise Advisor Mode. |
| **Over 7 days**          | **Expired.** Treat as a miss. Note "Found an outdated plan from <date>. Planning fresh." Go to Step 1.                                                                 |

Decision records found here become **PRIOR_DECISIONS**. They inform the plan and do not replace
it. A decision record that the running code contradicts is stale: say so in the plan and mark
it superseded in the record.

No hit, or nothing relevant: go to Step 1.

---

## Tool detection

Note which of these work this session. With `--no-research`, skip all external
web/search/fetch probes and research calls. Otherwise probe with the cheapest call.

| Flag                 | How to set it                                                       | Fallback if false                                  |
| -------------------- | ------------------------------------------------------------------- | -------------------------------------------------- |
| `HAS_FILES`          | You can list, search and read files. Always true in a coding agent. | None needed. This is the minimum.                  |
| `HAS_WEBSEARCH`      | A web search tool responds.                                         | Rely on built-in knowledge; note it in the report. |
| `HAS_FETCH`          | A page fetch tool responds (any scraper or plain fetch).            | Use search result snippets only.                   |
| `HAS_RESEARCH_STACK` | The `/research-stack` skill is installed.                           | Run 3 to 4 web searches yourself.                  |
| `HAS_SUBAGENTS`      | Your agent can start subagents, ideally in the background.          | Run each perspective yourself as a separate pass.  |

Paid search or scraping services are optional. Every step works with free web search and plain
page fetches, or with none.

---

## The five sources

### Source 1: codebase

**Focused goal** (one feature, component or system): one exploration pass. If your agent supports
subagents, use a fast read-only one in the background with this prompt:

```text
Analyze the codebase for everything related to: <GOAL>. Find:
1) all relevant files and their roles, 2) existing patterns and conventions,
3) dependencies and imports, 4) test patterns used nearby,
5) TODO, FIXME or HACK comments in this area.
Be thorough: file structure, function signatures, data flow, integration points.
```

**Broad goal** (system-wide, architecture): several calls at once.

- List source files by extension in the project root (for example `**/*.{ts,tsx,js,py}`).
- Search the goal's key terms across the codebase.
- Read the manifest and config files (`package.json`, `pyproject.toml`, `tsconfig.json`,
  `.env.example` or equivalents).

### Source 2: repository memory

Search the repo's own records of past decisions:

```bash
goal_terms="<goal terms>"                      # fill in before running
goal_term="<goal term>"                        # fill in before running
grep -rli "$goal_terms" .devproto/decisions docs/adr* docs/decisions* 2>/dev/null
git log --oneline -n 200 | grep -i "$goal_term"
```

Read the top 3 to 5 matches. Commit messages and ADRs often explain why a pattern exists.

### Source 3: existing plans and roadmaps

List and read the most relevant (max 3):

```text
.devproto/plans/*.md
.planning/**/*.md
docs/architecture*.md
docs/adr*.md
ROADMAP.md
TODO.md
```

### Source 4: research (conditional)

- Skip with `--no-research`. Force with `--research`.
- Otherwise run it only if the goal holds unknowns: a new technology, an unfamiliar pattern, an
  external service, a third-party API.
- With `/research-stack`: run it on the unknowns. Without it: 3 to 4 web searches plus a fetch of
  the best primary source (official docs over blog posts).

Research queries focus on best practices for the specific pattern, common pitfalls and
anti-patterns, performance characteristics, and (TECH mode) security considerations.

### Source 5: best practices

Skip this entire source with `--no-research`. Otherwise, if web search works:

```text
"<technology> <goal terms> best practices <current year>"
"<technology> <goal terms> common mistakes pitfalls"
```

### Fallback rules

- If any source errors, note which one and continue with the others.
- Do not retry a failed source. Move on with what you have.
- Track which sources succeeded, for the report.

---

## Degradation

| Source                 | If it fails                                        | Fallback                                                                                                                                    |
| ---------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Codebase exploration   | Large repo timeout or subagent error               | Targeted file listing and search on paths taken from the goal's keywords                                                                    |
| Repository memory      | No decision records exist                          | Skip. Note "no recorded decisions" in the report                                                                                            |
| Existing plans         | No plans folder, nothing relevant                  | Skip. Note "greenfield, no existing plans" in the report                                                                                    |
| Research or web search | Error or timeout                                   | Skip best practices. Rely on built-in knowledge and say so                                                                                  |
| Page fetch             | Not available or error                             | Use search snippets; cite them as snippets                                                                                                  |
| Best-practice search   | Error                                              | Skip. Note it in the report                                                                                                                 |
| Specialist board (3.7) | Pass fails, times out, or the lens file is missing | Skip Step 3.7 and log `specialist-lenses=skipped`. The plan ships without the specialist sections. The Step 3.5 perspectives are unaffected |

**Minimum viable pipeline**

- Always available: list, search and read files, plus built-in knowledge. That is a working plan.
- With repository memory: past decisions and patterns. A better plan.
- Full: plus research, best practices and an exploration subagent. A comprehensive plan.

**Complete failure**: if even the file tools fail, report what happened and produce a plan from
the goal description alone, clearly marked as ungrounded.
