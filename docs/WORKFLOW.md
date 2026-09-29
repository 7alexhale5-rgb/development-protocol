# How we run AI development day to day

`docs/STANDARD.md` says what "done" means. This page says how the work actually flows through
sessions, models, branches and people. It comes from a working practice that runs nine or ten agent
sessions at once, all day.

## 1. Plan first. It is 80% of the result

- Start every piece of work with a prepared prompt: the goal, the context, the constraints, links to
  what exists. A little direction up front saves hours of iteration later.
- Do the research and the planning before you run `/development-protocol`. The protocol builds what
  the plan says. A thin plan gives a thin build.
- Use your strongest model for reasoning, research and the spec. It has to account for every
  variable. Implementation of a good spec can go to a faster, cheaper model.
- If your agent has a goal mode, set the goal first, then run the protocol with full context, and
  let it work until the goal is met.

## 2. Work in phases

- Break a development cycle into three to five phases. Five at most. More means the plan is too big.
- Each phase ships one runnable thing and has a number that proves it moved.
- Do not stop to look at partial results. Let the phases finish, then review the whole, then iterate.
- To improve something, run the protocol again on it. You can set it to loop five to ten times:
  look for gaps, errors and simplifications, research the gaps, fix, repeat.

## 3. One primary session, many workers

- Group your sessions by project in the agent's sidebar or session list.
- Name one session **primary** for each effort. It holds the plan and the big picture.
- When a phase is done and reviewed, ask the primary to split the next work into components and write
  one handoff prompt per component. Start one new session per handoff.
- Each worker session knows the primary by name and reports back to it when finished, so you manage
  one conversation, not five.
- Workers commit only their own files, on their own branch, through a pull request. Never commit
  another session's uncommitted work.
- Cross-session messaging usually needs the worker to run without permission prompts. If a report
  never arrives, check the worker's permission mode first.

## 4. Never lose a session

- When a session nears the end of its context (around 90%), have it write a **resume prompt**: goal,
  done, next, open questions, constraints, and the exact files. Paste it into a fresh session.
- Switching accounts or tools mid-project: give the new session the list of session names (a
  screenshot works) and ask it to read all session logs, get fully up to date, and write one resume
  prompt per session. Start one fresh session per prompt.
- In tools that offer a deep link to a session, copy the link and hand it to the other tool to read.
  Named sessions are enough for a tool to find the right log.

## 5. Every change gets a second model

- The model that wrote the code does not approve it. Use a reviewer from a different model family:
  if you build in one vendor's agent, review with the other vendor's model, and the reverse.
- Keep a fallback reviewer for when one account is out of usage. A fresh session of a strong model
  with only the diff and the spec is the minimum.
- A third model through a router service is a cheap extra pass on large or risky diffs.
- Some models are better at some jobs. If one writes cleaner UI code in your tests, route UI work
  there. Measure it; do not assume.

## 6. Put each model on the right job

| Job                                                               | Model                                                        |
| ----------------------------------------------------------------- | ------------------------------------------------------------ |
| Reasoning, research, specs, architecture, final judgment          | the strongest model you have                                 |
| Implementing a clear spec                                         | a fast model is usually enough                               |
| Heavy reading: long documents, PDFs, transcripts, message history | a small fast model                                           |
| Scraping and crawling                                             | a scraping service does the work; a small model only reports |
| Review                                                            | a different family from the builder                          |

Current Anthropic lineup, checked on 2026-09-29 against Anthropic's models overview page
(re-check before relying on it; models change every few months):

| Model | API id | Good for |
| --- | --- | --- |
| Claude Fable 5.1 | `claude-fable-5-1` | the hardest reasoning and long agentic work; a strong independent reviewer |
| Claude Opus 5.5 | `claude-opus-5-5` | the everyday default for planning, building and judgment |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | fast implementation of a clear spec; parallel review workers |
| Claude Haiku 4.5 | `claude-haiku-4-5` | heavy reading and quick lookups |

## 7. Branches, pull requests and the team

- A branch is a sandbox copy of the code. Review it on your own machine (localhost), not in
  production.
- Merge to main through a pull request. The repo's checks run on the pull request. When main
  changes, the host (for example Vercel) redeploys production. A separate testing environment is
  optional, not required.
- Every contributor uses their own GitHub account, so history shows who changed what.
- Only work on a branch that nobody else is touching. Say it in the team chat before you start:
  "I am changing the pricing page today."
- Turn on GitHub notifications for pull requests, and actually read them, or route them to where you
  look. The PR list on GitHub is the history of record.
- A shared team workspace in your agent tool, with shared project folders, is the easiest way to
  split session work across people who all use the same tool.
- A board (for example Linear, a Kanban tool) helps once more than two people ship to the same repo.

## 8. Try three ways, then ask

- Before asking a teammate, try three genuinely different approaches: another tool, another angle,
  another way of splitting the problem. Then ask, with what you tried and what failed.
- Ask the agent the question the right way before asking a person. With enough patience and good
  questions it will usually find the answer.
- Let the agent find the tools. Tell it to search widely for anything that could help, and do other
  work while it looks.

## 9. Keep what you built

- When you abandon or pause something, put it in a backlog folder with a short note. Half-built
  systems become the first half of the next project.
- When the agent produces something excellent, tell it: "this is now the floor; never deliver below
  this." Save that as a rule so it persists.
- Read outcomes, outputs and results. Do not do by hand what the agent can do.

## 10. Keep the tools current

Every few weeks, or before a big build:

- Update the agent apps and CLIs.
- Reload plugins and MCP servers; check each connector still authenticates.
- Check skills and configs point at current model names. Models improve every couple of months; old
  pins waste that.
- Pull this repo and re-run `./install.sh --yes`. Read `CHANGELOG.md` for what changed.

## 11. Development is not operations

This stack covers the coding session. Watching production is a different job: use an error tracker
and uptime monitoring (for example Sentry and BetterStack) that send incident reports. A good build
process does not replace monitoring, and monitoring does not replace review.

## 12. Useful services

These make the research and build skills stronger. All optional.

| Service                                      | Use                                                                            |
| -------------------------------------------- | ------------------------------------------------------------------------------ |
| A scraping API (for example Firecrawl)       | Clean page text for research and competitor scans                              |
| A search-answer API (for example Perplexity) | Cited answers for the research skill; a small prepaid balance with auto-reload |
| A last-30-days social search skill           | What people said about a topic recently on Reddit, X and the web               |
| A RAM monitor                                | Many agent sessions use a lot of memory; watch and quit background apps        |
| A programmable mouse                         | One-press region screenshot, copy, paste and enter speed up agent work         |
