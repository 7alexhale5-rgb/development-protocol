# Client-site motion workflow

Use this when a brief calls for a website hero, a product explanation, a case-study film, a launch
clip or a footage edit. Keep the existing brief, design decisions and proof report. Add the fields
below only where they are missing. This is a production path inside `/design-stack`, not another
service, approval funnel or editor.

## What a tested pilot established (2026-10-28)

A pilot built a hero film from a public tutorial's method: reference-led storyboards, explicit
timing, loop review and iteration. The tutorial's HTML and animation-library stack was one
renderer option; the pilot used an offline canvas renderer driven by a deterministic clock. Two
real iterations established the reusable parts: real asset integration, a separate phone
composition, shorter text crossfades, a longer settled hold on the action, decoded-frame
repeatability, loop inspection and browser recovery. Those are observations about one pilot, not
universal creative rules or measured conversion gains.

## Insert into the existing process

| Existing point                   | Add                                                                                                   | Observable output                                           |
| -------------------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Strategy and scope               | User task, why motion helps, exact action, formats, asset rights, revision scope and costs            | The existing brief explains the benefit and the limits      |
| Step 4 references                | Inspect the production method, assets and meaningful transitions; record the source and timestamp    | A reference-to-build trace                                  |
| Step 5 decisions                 | Storyboard with trigger, transformation, easing, settled reading time and failure states              | One approved client direction, no borrowed brand            |
| Step 6 generate                  | Prove the hardest shot with real assets, then extend one clock across the scenes                      | Editable source and repeatable render commands              |
| Step 7 verify                    | Actual frames, transitions, loop, browser controls, recovery, performance and task completion         | Evidence tied to source and export hashes; limits visible   |
| Step 9 persist and handoff       | Package source, fonts and licenses, media, posters and revision notes                                 | The client can revise without rebuilding the toolchain      |
| Case study or quality audit      | Record user-task evidence and post-launch outcomes separately                                         | No conversion claim from craft or from a source's popularity |

Keep one brief and one proof record, filed where the project's routing map says.

## Choose the smallest production path that serves the brief

- **Native CSS or the Web Animations API:** interactive feedback, state changes and navigation.
  Keep interaction immediate and meaningful. This is not the rendered film clock.
- **Code-rendered film:** exact typography, product graphics and repeatable timed edits. Reuse the
  project's existing HTML animation, video-as-code or canvas renderer when it fits.
- **Mixed media:** owned footage plus code-rendered type and graphics. Resolve crops, licenses,
  color and audio before the final export. If new generated media is needed, confirm the tool,
  its cost and the asset rights first.
- **Recorded-video edit:** trim and assemble source footage; add readable titles and accessible
  alternatives. Do not regenerate footage merely to use a generation tool.
- **Interactive 3D or scroll film:** choose it only when direct user control is part of the story.
  Preserve native scroll, visible content and a still fallback.

## Author and render

1. Set the client-specific composition, exact copy, owned media and the primary HTML action. Keep
   one project's logo, type and palette in that project only.
2. Write shot boundaries, what each transition explains, and the period when all required text
   is fully settled. Preview the densest shot at the actual phone display size. The pilot's
   three-second hold is not a minimum for every message.
3. Use one explicit timeline. Drawing any timestamp must not depend on earlier frames. Pin
   dependencies and fonts, wait for assets to load, reset drawing state between frames, and seed
   any randomness. No network calls, wall clock, timers or media playback clocks inside the draw.
4. Render a short hard slice, inspect it, then render both final compositions (wide and phone).
   H.264 with yuv420p and faststart is the tested compatibility path; choose resolution, frame
   rate, quality and extra codecs against the target device and budget.
5. Review a contact sample every half second, plus native-frame strips around each change and
   the loop boundary. Record sampled and reviewed counts separately. Watch real playback. A
   perfect first-frame to last-frame match does not prove a smooth seam, safe flashing,
   readability or good pacing.
6. Fix concrete failures and recheck the affected evidence. There is no mandatory three rounds,
   arbitrary score gate, fixed spring curve, always-moving rule or compulsory audio.

## Build the page around usable content

Keep the message, navigation and action in semantic HTML. A film must not delay a task or
pretend to be a working control. Use a responsive still with reserved dimensions before the
media loads. Offer explicit Play and Pause for ongoing motion, and keep an intentional pause
across resizing and tab visibility changes. Under reduced motion, at load or when the setting
changes, stop automatic motion; only an explicit Play opts in. Handle a rejected play, missing
media and Retry. Keep focus when a control is replaced. Clean up the player in the framework's
unmount step.

A decorative muted film can be hidden from assistive technology only when its meaning is also in
the HTML. Informative or narrated films need proper controls, captions or transcripts and other
accessible alternatives. `preload=none` is a hint, not a zero-transfer guarantee; when that
guarantee is required, set the source only after an explicit Play or a measured visibility rule.
Load below-the-fold media only when useful, and do not preload every format.

Set a measured first-load media budget in the brief, then inspect network transfer and lab
Largest Contentful Paint (LCP) and Cumulative Layout Shift (CLS). Field performance needs real
traffic; a missing Interaction to Next Paint (INP) value stays unknown. The pilot's combined
exports of about 1 MB are evidence about the pilot, not a site budget.

## Brief fields

Fill these in the existing brief. They are a starter, not another interview.

- Client, approved brand source, asset rights.
- User and task: what must visitors understand or do?
- Why motion helps this task; the static alternative.
- Lane: CSS or animation-API feedback, rendered graphics, mixed owned footage, edited footage, or
  an interactive scene.
- Exact copy and the semantic HTML action.
- References and their observed production method, with timestamps.
- Desktop and phone composition, safe text area, languages.
- Film duration, reading hold, transition intent, playback and loop behavior.
- Initial still, reduced-motion still, missing-media still.
- First-load and total media budgets, target device and network, lab measurement method.
- Required browsers and devices, and field-measurement limits.
- Audio, caption, transcript and audio-description needs.
- Acceptance: the task completes without watching, text is readable at target size, nothing
  clips, and controls and recovery states work.
- Baseline and comparison method; no conversion claim without measured evidence.
- Editable handoff, revision scope, owner, costs.

Storyboard columns: time in and out, purpose (the one thing this shot explains), exact copy and
owned assets, trigger (clock or user action), transformation and easing with a reason, settled
reading time (measured after all required content settles), the phone change, the reduced-motion
and failure state, and the check that proves the shot.

## Acceptance checks

Record evidence in the project's existing verification report. A pass belongs to the exact source
and export hashes tested.

**Render**

- Pin dependencies; record runtime and encoder versions and font and asset hashes.
- Render twice and compare decoded frame hashes; file hashes alone can differ on metadata.
- Confirm frame count equals duration times frame rate, even dimensions, codec and pixel format.
- Confirm the first and last frames match, then inspect the native frames around the loop and
  watch playback. Endpoint equality is not proof of a smooth seam or safe flashing.
- Extract every half second, count the expected samples from the media duration, and review every
  contact sheet including the final partial interval. Record extracted and reviewed counts. For
  long films, page through all frames; never claim a full review from the first sheet.
- Review native-frame strips around fast transitions, reading holds, text overlap and crops.
  Pixel checks cannot judge brand or comprehension.

**Player and page**

- At 390, 768 and 1440 CSS pixels plus any brief-specific devices: no overflow, the right source,
  a readable layout.
- Load with reduced motion on, and change the setting during playback; both must stop automatic
  movement. Explicit Play can opt in. Turning the setting off must not restart playback by
  surprise.
- Pause, cross the responsive breakpoint and come back: the pause holds. Enter and Space work and
  focus stays visible.
- Block the video request: the still and the HTML action survive; clear the block and Retry
  recovers. Test a rejected play and disabled JavaScript too.
- Check that hiding the tab pauses, repeated loops behave, the source switch works, and the player
  cleans up in the real framework.
- Exercise the real business action to its result. A fake form, a fixture anchor or a download
  does not prove a lead flow.
- Check contrast, target size, zoom, focus, flashes and captions where they apply. WCAG 2.2.2
  (Level A) covers automatic movement longer than five seconds beside other content; 2.3.3 is
  Level AAA. A reduced-motion baseline is a team choice, not proof of full conformance.

**Delivery**

- A private, phone-reachable HTTPS preview; confirm its access policy both by API and in a
  browser. Local fixture checks are not hosted proof.
- Measure first-load bytes and lab LCP and CLS under recorded conditions.
- Test target phone browsers and hardware before promising device coverage. An emulated viewport
  proves layout only.
- Deliver source, lockfile, render commands, media and posters, licenses, hashes, storyboard and
  checks with their limits.
- Promise no universal film length, spring curve, soundtrack, aesthetic score, round quota or
  conversion gain. Compare a static and a motion version with representative users before
  claiming better understanding or more leads, and record tasks, sample size, failures and
  limits.

## Expert basis and limits

- [Nielsen Norman Group, the role of animation and motion in UX, 2020](https://www.nngroup.com/articles/animation-purpose-ux/):
  subtle motion can clarify state and relationships, but it also draws attention. Apply the
  purpose test. This is expert guidance, not a film conversion study.
- [Nielsen Norman Group, animation duration, 2020](https://www.nngroup.com/articles/animation-duration/):
  document trigger, transformations, duration and easing. UI transition timings do not set a
  whole film's length.
- [Apple Human Interface Guidelines, Motion](https://developer.apple.com/design/human-interface-guidelines/motion):
  preserve people's ability to act. Website use here adapts app guidance.
- [WCAG 2.2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide) and
  [2.3.3 Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html).
- [MDN, autoplay guide](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay),
  [web.dev, video performance](https://web.dev/learn/performance/video-performance) and
  [web.dev, Web Vitals](https://web.dev/articles/vitals): design for playback denial, budget
  media, and keep lab evidence separate from field evidence.

Shipped sites you study are design references, not usability validation or licensed assets.
