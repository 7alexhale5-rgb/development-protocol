# Design quality floor: creative freedom, finished work

The shared starting point for design work: products, websites, decks and visual artifacts. It is
a floor to improve on, not a ceiling. It replaced an earlier set of blanket aesthetic bans (fixed
palettes, banned fonts, radius and type-size counts) on 2026-09-23, after those bans produced
safe, flat, interchangeable screens.

Read this once per design task. `/design-stack` applies it inside its existing steps. It adds no
approval round, no scorecard and no new receipt format.

## Contents

- [The standard covers the whole working result](#the-standard-covers-the-whole-working-result)
- [Measure outcomes and strength of proof](#measure-outcomes-and-strength-of-proof)
- [Product interfaces: tasks, records, controls](#product-interfaces-tasks-records-controls)
- [Craft and performance are separate acceptance requirements](#craft-and-performance-are-separate-acceptance-requirements)
- [What makes this the floor](#what-makes-this-the-floor)
- [Creative freedom is the default](#creative-freedom-is-the-default)
- [How to work from here](#how-to-work-from-here)
- [Understand and reproduce the production method](#understand-and-reproduce-the-production-method)

## The standard covers the whole working result

Reference images are reminders of ambition, not the full definition of quality (clarified
2026-09-27). Apply the standard to code, configuration, data, design, production workflow and the
end-to-end result together. Looking right cannot make up for a broken action or unsupported data.

Use the existing brief and proof notes to connect:

- **Sources to decisions.** Pick relevant references (live products, source studies, recipes).
  Record their links, the method adopted and its limits. Read the actual source; a screenshot or a
  catalog count does not show the source was used. Choose for the project's needs, not taste.
- **Code and configuration to behavior.** Inspect the joined components and service contracts.
  Check the real runtime, dependency locks, required settings, permissions and provider
  availability without exposing secrets. An installed tool, a mock response or a green build is
  partial evidence only.
- **Data to claims.** Trace displayed facts and AI citations to their sources. Test realistic
  input shapes, missing or stale data, scope isolation, and saved values. Label fixtures and
  generated examples as such.
- **Design to the delivered experience.** Review the real assets, composition, responsive states,
  accessibility, loading, errors and recovery in the running product. Keep the project's own
  identity.
- **Workflow to repeatable proof.** Prove the hardest piece early, then run the complete user
  journey through to its real result. For saved work, reload and read it back from the real
  store. Include meaningful failure paths. Tie evidence to the tested revision and environment;
  rerun affected checks after changes. A local-only result stays labelled local-only.

Report which of these are proven, partial or untested. If the app cannot run or a service is
down, keep that proof marked incomplete. A skipped check never becomes acceptance. A check that
guidance is reachable proves only that, not that a session followed it or that a product works.

## Measure outcomes and strength of proof

Keep the effort proportional. A small visual edit needs its intended improvement, relevant source
context and the affected render and interaction checks. It does not need an experiment or a
scorecard. A substantive workflow needs the full journey, saved-result read-back and recovery
where relevant. Research-only and static artifacts are judged as what they are, without inventing
runtime evidence for features they only describe.

### Define success before viewing results

State the user, the task, the expected usable result, the material errors and the acceptance
criteria before the candidate is graded. Tie evidence to revision, environment, input and rubric
version. Freeze comparison criteria and held-out cases before any candidate output is seen.
Measure a comparable baseline before changing anything. If the change already happened or no
valid baseline exists, label the work prospective-only and report absolute acceptance. Never
invent a before and after gain, and never weaken controls to get a baseline.

### Keep critical failures visible

Unauthorized access, lost or silently corrupted data, materially unsupported claims, wrong
material calculations and false completion block acceptance of the scope they touch. Required but
untested checks are unknown, never passes. Do not average these away with looks, speed or a high
score. A score is evidence, never permission to send, spend, grant access or deploy.

### Separate quality from evidence

For a substantive assessment, keep separate rows for research, code, configuration, data,
design and usability, and workflow and handoff, as they apply. Record quality as:

| Mark | Meaning                                                          |
| ---- | ---------------------------------------------------------------- |
| U    | Unknown                                                          |
| 0    | Fails                                                            |
| 1    | Needs substantial correction                                     |
| 2    | Usable with a specified minor correction                         |
| 3    | Meets the written criteria without correction on the case tested |

Link the supporting artifact and the next corrective action. There is no universal weighted score
and no aesthetic grade.

Describe evidence strength separately, from weakest to strongest: an assertion or plan; an
inspectable source or local check; an observed complete journey in a named environment; repeated
relevant cases with independent checking. Fixtures and local-only results stay labelled. Repeated
local checks do not prove an untested live provider. Automated correctness and model agreement do
not prove human usability. A top rating on one case does not mean perfect, generally reliable or
approved for release.

### Measure useful outcomes

Pick the smallest relevant set:

- **First-pass usable results:** fully correct outcomes without unplanned repair, divided by all
  attempted cases, including failed and abandoned ones.
- **Human correction effort:** time spent finding and fixing errors per attempted case. Keep
  failed cases. Separate human time from automated work.
- **Time to accepted result:** elapsed time including retries and correction. Report unfinished
  cases separately rather than counting them as fast successes.
- **Material errors:** cases with material factual, scope, calculation or persistence defects,
  divided by all attempted cases.
- **Independent handoff success:** someone new to the work can name the next task, scope,
  dependencies, access limits and acceptance test.
- **Cost per accepted result:** all run, retry and review costs divided by accepted results.
  Undefined when none are accepted. Unknown costs stay unknown.

Set improvement targets after the baseline and before looking at candidates. Time or cost gains
count only if correctness, boundaries and completion do not regress. Report numerator,
denominator, case count and run count separately. For variable AI comparisons, use repeated fresh
runs, paired uncertainty, blind and position-swapped judging, untouched held-out cases, negative
controls and a calibrated judge. Uncalibrated AI ratings are advisory. One project's result does
not prove a cross-project improvement. Repeating a deterministic check is not an independent
sample of user outcomes. Call an inconclusive comparison inconclusive.

### Make failures change the result

Fix critical, frequent or costly failures first. Reproduce the case, fix the cause, rerun that
case and the affected regressions, then check fresh cases. Once a held-out case has guided a fix
it is a development case; replace it before the next unbiased comparison. Keep failures on record
as well as successes. Keep a fix only when the intended outcome improves without a material
regression. Report the next most valuable repair, not a rising total score.

## Product interfaces: tasks, records, controls

This section applies to software screens, prototypes, dashboards and admin tools.
It overrides storytelling and promotional copy defaults for operational UI. Marketing
pages, documentation, source quotations and user content keep their own purpose.
Classify each region by the user's task. Operator plans are not product scaffolding.

- Identify the user, record, primary task, available actions and resulting state.
- Inspect the project's real component inventory before writing custom controls.
  Reuse or extend tables, forms, toolbars, tabs, dialogs, drawers and feedback where
  they fit. Record the source in the existing brief. A library install is not proof
  that its components were used. Do not add dependencies to meet a component count.
- Put the working queue, record, editor or chart in the main work area. Keep related
  evidence beside the task or in a reachable detail view. Avoid repeating facts in
  oversized cards. A table is useful for comparisons; it is not every screen's layout.
- Use headings that name destinations or records, and buttons that name actions.
  Supporting subtitles are optional. Remove slogans, poetic headings, repeated benefit
  claims and descriptions of how the screen was built. Replace excess prose with the
  control the task needs. Shorter copy alone does not make a better interface.
- Keep labels, useful context, clear uncertainty, warnings, validation and recovery.
  Place optional background in contextual help. Do not hide essential warnings.
  Show sample-data or disconnected-service status at its relevant persistent scope.
- Define keyboard, focus, selection, filters, empty/loading/error states, permissions
  and save feedback. Controls must work or show why they are unavailable. Preserve
  drafts through failure and read saved results back from the intended store.

## Craft and performance are separate acceptance requirements

A screen can pass copy and accessibility checks and still miss the design floor.
A rejected operational screen may have short labels but waste its space on a large
status card. Keep that as a task regression case, not a universal card-size rule.
Do not replace prose with empty boxes or reduce every workflow to a bare table.

Before changing a screen family, freeze the user task, representative data, work that
must be visible together, relevant viewports and failure cases. Measure a comparable
baseline. Use the project's own accepted renders and actual component sources.
Compare native-size renders at wide, normal application-panel and phone widths.
Check hierarchy, useful space, typography, alignment, assets and control detail.
Exercise long records, missing data and keyboard use. Fix the observed weak areas.
A screenshot count, source lint or installed library cannot establish visual fidelity.

Keep typography, color, gradients, depth, imagery, motion and layout open. Judge CSS
techniques such as calc, negative spacing and absolute positioning by their behavior.
Do not flatten the work to satisfy a font count, type ratio or palette detector.
Do not add motion or components only to make a screen look complex. Existing tokens
support a project's identity and may evolve during an authorized redesign.

Choose relevant performance budgets in the existing brief before grading the candidate.
Measure initial content, response to the main action, layout stability, asset transfer
and time to the saved result where they matter. Record the revision, device, viewport,
cache state, network and CPU settings, run count and failures. Compare like conditions.
Include cold load, larger data and recovery when they affect the task. Optimize media,
fonts, rendering and network work before sacrificing visual craft.

Keep field measurements from real users separate from controlled lab tests. A browser
harness click duration is not Interaction to Next Paint (INP), a responsiveness metric.
Automated task time is not human completion time. Missing measurements remain unknown.
Speed never cancels data loss, wrong results, inaccessible controls or an unusable screen.

Use existing browser tests to check task-specific visible work, enabled actions and
measured budgets. Include a rejected case and a useful case with different visual choices.
Keep visual comparison, full task behavior, access/data proof and performance separate.
Source checks prove only their declared assertions. Human usability still needs human
observation. No new approval ritual, mandatory scorecard or aesthetic threshold is added.

## What makes this the floor

- **Composition with a point of view.** A strong headline, a dominant work area, distinct
  supporting regions and a deliberate rhythm. The eye knows where to go. The page feels designed,
  not assembled from identical cards.
- **Rich, useful surfaces.** Evidence chips, imagery, progress tracks, comparisons, diagrams and
  workspaces often explain the task better than repeated plain lists. Use tables and lists when
  they are the best tool, not as the automatic layout.
- **Finished craft.** Substantial type, optical alignment, clear contrast, considered density,
  coherent color, fine detail and polished interaction states. Typography, depth, motion and
  imagery can all carry meaning and character.
- **Function that earns the interface.** Prominent controls do useful work. Show clear results,
  recovery and the next move. A strong concept must become an equally convincing working
  experience.
- **AI inside the work, when useful.** Bring context, sources, comparisons, editable drafts,
  proposed changes and next actions into the task, where they help the user.

Carry this level of fidelity into each project. Do not clone one product's layout, palette,
brand or feature set into every brief.

## Creative freedom is the default

Explore color, fonts, light or dark surfaces, gradients, shadows, depth, expressive layouts,
motion and imagery freely. There is no universal forbidden palette, font family, radius count,
type-size count or display-to-body ratio. No permission or waiver is needed to depart from an old
aesthetic default.

Choose what serves the audience, the brand and the task. Existing tokens keep a product coherent;
they can change during an authorized redesign. A client brief is the source for that client's
identity. A studio's own brand is for its own products, not a house skin for everyone else's.

Keep the work legible, accessible, responsive and usable. Keep data truthful, previews honestly
labelled, and permissions and user control intact. Creative freedom never implies permission to
send, spend or change production.

## How to work from here

Start from a strong rendered idea. Use relevant references and visual tools early. Explore
directions when that helps, choose with judgment, and build. Carry the visual quality through to
the working page. Compare the current render with the reference, then fix what looks weak or
unfinished.

Automated style scores are optional observations, never taste verdicts and never a reason to
flatten a design. Code, accessibility and behavior checks keep their own purpose.

For each meaningful pass, pursue one concrete improvement beyond the current floor: a stronger
composition, a clearer story, a better interaction, a useful AI capability or more convincing
detail. Keep what improves the result.

## Understand and reproduce the production method

Saving a beautiful screen is not enough (clarified 2026-09-23). The standard includes knowing how
the result beneath that screen is produced. A reference is both a visual target and an
engineering research task.

1. **Find the actual work.** Follow the source: the live site, the repository, delivered code,
   assets and official tool instructions. Use the real interactions. A showcase recording, an
   installed plugin or a stated stack does not show how a product works. Search adjacent sources
   when the first view hides the mechanism.
2. **Separate the layers that create the effect.** Work out what comes from photography,
   generated images, video, 3D, typography, layout, motion code, state and backend services.
   Inspect timing, media encoding, responsive changes, loading and failure behavior. For AI
   features, trace context retrieval, permissions, model calls, citations, proposed changes and
   persistence.
3. **Recover the production inputs.** Keep source links, asset files and their rights, prompts,
   reference images, model and settings where visible, tool versions, dependency locks,
   transformations and exact build commands. Keep successful outputs. If a provider hides its seed
   or model, record that limit; the same prompt does not promise the same generated asset.
4. **Test the hardest mechanism early.** Build and run a small real slice with the method you
   inspected. Exercise forward and reverse states, inputs, keyboard, narrow layouts, slow or
   missing media and data, and recovery. Connect a business action to its real result before
   calling it working. A fixture proves fixture behavior; a rendered image proves appearance.
5. **Carry the method into the full build.** Use the project's brand, stack and business
   contracts. Rebuild interactive text and controls as real UI. Produce the assets that carry the
   visual quality, then connect the code around them. Compare the working result with the
   reference throughout. A simpler fixture proves a mechanism, not full fidelity.
6. **Keep knowledge another task can use.** Add the source-to-effect map, runnable commands, proof
   paths, dependencies and known gaps to the design brief and asset record. Keep four things
   distinct: observed original behavior, inspected original code, a proposed reconstruction, and
   a reconstruction actually tested.

If the original source or generation history cannot be recovered, state exactly what is missing
and prove your own implementation of the effect. Do not claim the original process is known, or
that a visual match proves hidden business behavior. Settle the unknown with the smallest useful
experiment.
