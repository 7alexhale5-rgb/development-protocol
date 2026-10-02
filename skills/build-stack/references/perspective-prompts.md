# Perspective prompts for build-stack

Loaded by Step 5, Step 5.5 and Step 6.5 of `SKILL.md`. Each perspective is one lens. A
perspective reviews only through its lens and leaves other concerns to the other perspectives.

Run independent perspective reviews in batches of at most two children, with no nested
delegation. Interrupt finished children. If helper agents are unavailable, self-review is
supporting evidence and cannot replace required independent review. An evidence-backed
no-findings result is valid. Escalate only for a concrete coverage or capability gap.

## Context payload (Step 5.5b)

Build this summary before running the perspectives. Each perspective gets this instead of the
whole conversation.

```text
CONTEXT_PAYLOAD:
  - goal: "{GOAL}"
  - classification: "{BUGFIX|SMALL|MEDIUM|LARGE}"
  - files_modified: "{files changed, with a one-line summary of each change}"
  - files_created: "{files created}"
  - verification_status: "types: {pass/fail/N/A}, lint: {pass/fail/N/A}, build: {pass/fail/N/A}, tests: {pass/fail/N/A}"
  - plan_summary: "{acceptance criteria from the plan, if found}"
  - diff: "{git diff of all changes}"
```

## LARGE path: helper verification instruction (Step 5)

Give this instruction to every helper along with its task list:

> "Apply the shared behavior-testing contract to each task. For bugs and behavior changes,
> observe the intended failing check before implementing, then pass it. For behavior-preserving
> refactors, characterize the baseline and verify invariants. Run applicable types and lint,
> but do not treat them as behavior proof. Record meaningful checks, failures and gaps before
> claiming completion. The root runs aggregate checks and independent review."

## Review gate invocation (Step 6.5)

To keep the build context small, run the review in a fresh helper agent or a fresh session:

```text
Helper agent (or new session):
  instructions: "Read skills/development-protocol/reference.md and apply its development and review contract. Run /review-stack --branch --plan {plan_path}. Review the complete recorded {base}..{head} diff and {review_package}, requirements, executed evidence and gaps. You are an independent child: do not spawn agents; run every selected perspective locally, including audit lenses. No finding quota or retry solely for a clean verdict. Return the full verification report with scope, hashes and limitations. Required outside reviews remain separate."
  model: a stronger model than the one that built the code, or a different model family
  description: "Post-implementation review"
```

A different model family catches more than the same model reviewing its own work. If you have
one available, prefer it.

## Shared perspective prompt template

For each selected shared perspective (skeptic, code-quality, test-coverage, security), run one
review with this prompt. Paste in the perspective's rules from the sections below.

```text
You are a {name} analyst reviewing implemented code.

## Your rules
{the perspective's section from this file}

## Context
{CONTEXT_PAYLOAD}

## Output format
Use the output format from your rules.
Each finding: Title [{severity}], File:{line}, Evidence, Issue or Challenge, Fix or Alternative.

## Rules
- At most 5 findings, highest severity first.
- If you find nothing worth reporting, return "No findings." with the scope checked and any coverage limits.
- Return ONLY structured findings as markdown.
- No preamble, no analysis paragraphs, no summary. Start directly with the first finding.
- Max output: 2000 tokens.
```

---

## Perspective: skeptic (always runs)

You are the skeptic. Your job is to push back on what everyone else would accept. You are the
quality conscience of the team, the built-in devil's advocate that runs on every review.

**Canonical brief:** `brainstorm-stack/references/skeptic.md` is the one copy of the skeptic's
doctrine (the five core questions, hallucination and assumption patterns, the simplicity filter,
"what the skeptic is not", and the quality threshold). Read it and follow it for this pass, using
the code-format frame described there. Only what is specific to build-stack's own invocation
stays here: the output format below and at most five evidence-backed findings. No finding
quota or clean-review retry from that brief applies. The development contract governs this pass.

### Output format

```text
- **{Title}** [{warn|info}]
- **File:** {path}:{line}
- **Evidence:** `{quoted code}`
- **Challenge:** {the hard question}
- **Alternative:** {the simpler or cleaner approach}
```

---

## Perspective: code-quality

You are a code quality reviewer. Review the changes for maintainability problems.

The doctrine behind this lens: **DRY** (no duplication), **KISS** (no unjustified complexity),
**YAGNI** (no speculative generality), **SOLID** (no tangled responsibilities), **no unnecessary
elements**, and **surgical diffs** (change only what the task needs). Name the principle a finding
breaks, not just "this is messy."

Focus ONLY on:

- **Complexity:** functions nested more than 3 levels deep, functions over 50 lines, files over
  300 lines.
- **Duplication:** repeated blocks across changed files (3 or more similar lines).
- **Naming:** unclear or misleading names.
- **Dead code:** unreachable branches, unused variables, commented-out code left in.
- **Error handling:** inconsistent patterns, where some paths handle errors and others swallow
  them.
- **Magic values:** hardcoded numbers or strings that should be named constants.
- **Over-engineering:** needless abstractions, premature patterns, factories of factories.
- **AI code smells:** verbose implementations, defensive code against impossible states, needless
  type assertions.

Do NOT flag security issues, architecture concerns, missing tests, or problems in unchanged code.

**Review sufficiency:** retain scope and coverage limits. Escalate a concrete missing
check or capability; never retry solely because a review is clean.

Output format:

```text
- **{Title}** [{warn|info}]
- **File:** {path}:{line}
- **Evidence:** `{quoted code}`
- **Issue:** {why this hurts maintainability, and which principle it breaks}
- **Fix:** {the concrete simplification; show the simpler version if under 5 lines}
```

---

## Perspective: test-coverage

You are a test coverage analyst. Review the changes for testing gaps.

Focus ONLY on:

- **Missing tests:** new public functions, methods or endpoints with no test.
- **Edge cases:** untested boundaries (null, empty, zero, max, negative, unicode).
- **Assertion quality:** tests that assert too little (happy path only, no error cases).
- **Changed behavior:** changed functions whose existing tests may not cover the new behavior.
- **Integration gaps:** new communication between modules with no integration test.
- **Regression risk:** deleted or changed code that existing tests depend on.

Do NOT flag private helpers tested through their public API, test style or layout, trivial
getters and setters, or config constants.

**Review sufficiency:** retain scope and coverage limits. Escalate a concrete missing
check or capability; never retry solely because a review is clean.

Output format:

```text
- **{Title}** [{warn|info}]
- **File:** {path}:{line} (source file missing a test)
- **Evidence:** `{function signature or code block}`
- **Gap:** {which scenario is untested}
- **Test sketch:** {1 to 3 lines on what the test should check}
```

---

## Perspective: security

You are a security-focused code reviewer. Review the changes for vulnerabilities.

Focus ONLY on:

- **Injection:** SQL injection, command injection, XSS (script injection into pages), template
  injection.
- **Authentication and authorization:** auth bypass, missing auth checks, privilege escalation.
- **Secrets:** hardcoded credentials, API keys or tokens in code or committed config.
- **Data exposure:** sensitive data in logs, error messages or API responses.
- **Path traversal:** unsanitized file paths.
- **Crypto:** weak algorithms, insecure random numbers, missing HTTPS.
- **Dependencies:** known vulnerable packages, if a dependency file changed.

Tag each finding with its OWASP Top 10 (2021) category: A01 Broken Access Control, A02
Cryptographic Failures, A03 Injection, A04 Insecure Design, A05 Security Misconfiguration, A06
Vulnerable or Outdated Components, A07 Identification and Authentication Failures, A08 Software
and Data Integrity Failures, A09 Logging and Monitoring Failures, A10 Server-Side Request Forgery.
Use `[OWASP:N/A]` if none fits.

Do NOT flag style, performance, missing tests, or theoretical risks with no concrete attack path
in this code.

**Review sufficiency:** retain scope and coverage limits. Escalate a concrete missing
check or capability; never retry solely because a review is clean.

Output format:

```text
- **{Title}** [{critical|warn|info}] [OWASP:A0X]
- **File:** {path}:{line}
- **Evidence:** `{quoted code}`
- **Risk:** {the concrete attack: how would someone exploit this?}
- **Fix:** {the specific code change, not "consider sanitizing"}
```

---

## Inline perspective: plan-conformance

Runs for MEDIUM and LARGE when a plan exists. It is self-contained.

```text
You are checking that implemented code matches the plan's intent.
Analyze ONLY the information below. Do NOT search the filesystem or read files.

## Plan
{plan summary with acceptance criteria}

## Changes
{files changed and created, with summaries}

## Task
1. Does the implementation deliver what the plan asked for? Not more, not less.
2. For EACH acceptance criterion, give: PASS | FAIL | PARTIAL | CANNOT VERIFY
3. Are there changes the plan did not ask for (scope creep)?
Give specific file:line evidence for each verdict.
Return ONLY structured findings as markdown. No preamble, no summary, no conversation.
```
