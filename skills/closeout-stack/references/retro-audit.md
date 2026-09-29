# Closeout Stack: Retro Audit Detail (Step 7.5)

## Contents

1. The six categories
2. Strict silence rule
3. Anti-patterns
4. Output target
5. Failure isolation

---

## The six categories

Audit this session's transcript across these six categories. **Stay silent unless a finding
traces to a specific moment.**

### 1. Skill or doc instructions against reality

Did a documented step fail when run exactly as written? A wrong command, a missing flag, an
unsupported path, a stale name, a broken example. These are the most valuable findings. They
stop the next run from hitting the same wall.

### 2. User corrections (process or structure only)

When the user pushed back, was it a _process or structural_ correction ("we should use approach
X", "rename that file", "this default is wrong") that means a doc or default needs to change? Or
was it a style or content choice for this session only? Surface only the structural ones.

### 3. Silent failures found the hard way

A test that "passed" but produced wrong output. A lint warning that turned out to be critical. A
flag that behaved unexpectedly. Each should become an explicit failure mode written into the
relevant skill or the project's agent instruction file.

### 4. Drift between docs

README, agent instruction file, skill files, project state, tooling. If any pair was out of sync
(a README names a renamed function, a doc points at a stub file), flag it.

### 5. Workflow friction

Steps that took several tries. Loops that felt heavy. Decisions that were ambiguous because the
relevant doc said nothing about them.

### 6. Patterns that emerged

A new component, helper or technique built from scratch during the session that would be worth
saving to a shared library or doc for reuse.

---

## Strict silence rule

Emit a finding ONLY if you can cite a specific moment in the transcript: a tool call that
errored, a user correction of a documented step, an instruction whose exact execution failed, a
doc you read that turned out wrong, a fresh helper you built. **Inferred friction with no cited
moment means silence.**

---

## Anti-patterns

- **Don't pad the list** with weak items to make it feel substantial. A 2-item list is fine. A
  0-item list is fine.
- **Don't surface style or content preferences** as skill issues. Those are per-session choices,
  not project-level changes.
- **Don't propose new skills** unless the session exposed real friction the skill would have
  prevented. "Could be nice to have" is not a finding.
- **Don't speak when there is nothing worth saying.** Silence is a valid output.
- **Don't recommend changes you cannot justify** with a specific moment from the session.
- **Don't auto-implement** the suggestions. Surface them. The next session decides which to
  apply, when and how. The retro is signal, not action.
- **Don't repeat findings** inside the same handoff. If a finding was already raised in an
  earlier `## Retro Findings` block in this handoff (a second closeout in the same session),
  mention it once ("still applies from the earlier retro: X") instead of deriving it again.

---

## Output target

If findings exist:

1. Read the handoff at `STATE_PAYLOAD.handoff_path`.
2. If a `## Retro Findings` section already exists (a second closeout in the same session), add
   a `### Update HH:MM` subsection inside it. Otherwise add a fresh `## Retro Findings` section
   before any `## Related` section or end-of-file footer.
3. Format the findings as below. Group them by category when there are 5 or more. Otherwise use a
   flat numbered list. Each item is one or two short lines, action-oriented, and traceable to a
   transcript moment.

```markdown
## Retro Findings

<Optional one-sentence framing if something was surprising; skip otherwise.>

### Stale docs

1. **<file or doc name>**: what is wrong, what to change.

### Skill or doc instructions that don't match reality

2. **<name>**: what failed, what the actual behavior is.

### Silent failures

3. **<failure>**: what happened, what to write down.

### Workflow friction

4. **<friction>**: what felt heavy, what could ease it.

### New patterns

5. **<pattern>**: what was built, where it should be saved.
```

4. Set `STATE_PAYLOAD.retro_findings = {count: N, in_handoff: true}`.
5. Add the optional `Apply:` line to the resume prompt (see `templates.md`).

If there are no findings (the silence path), set `STATE_PAYLOAD.retro_findings = null`. Do NOT
write a "no findings" note into the handoff. Silence is the valid output.

---

## Failure isolation

Step 7.5 is non-critical. Any error during the audit, the handoff read or write, or the dedupe
scan must:

1. Set `STATE_PAYLOAD.retro_findings = null`
2. Add `{step: "7.5 retro", reason: "<one line>"}` to `STATE_PAYLOAD.failures`
3. **Continue to Step 8.** Do not stop the pipeline.

Step 10 always fires. The `Apply:` line is left out when `retro_findings` is null. The 10b report
shows `✗ failed (<reason>)` so the failure is visible at a glance.
