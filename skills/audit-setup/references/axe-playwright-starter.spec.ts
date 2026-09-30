// smoke.spec.ts - accessibility smoke test scaffolded by /audit-setup.
//
// Run: npx playwright test --grep @a11y
// or define a Playwright project named "a11y" and run: npx playwright test --project=a11y
//
// Prereqs: @playwright/test and @axe-core/playwright as devDependencies.
// Docs:    https://www.npmjs.com/package/@axe-core/playwright
//
// /review-stack --audit reads axe violations by impact: "critical" and "serious"
// block at a hard gate, "moderate" warns, "minor" is informational.
//
// Keep ROUTES tight (4 to 7 key routes). axe takes about 1 to 2 seconds per warm route.

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const ROUTES: { name: string; path: string }[] = [
  { name: 'home', path: '/' },
  // Add the routes real users hit most.
];

// WCAG 2.1 AA is the default bar. Extend tags only if you target AAA.
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

for (const route of ROUTES) {
  test(`@a11y ${route.name} has no critical/serious violations`, async ({ page }) => {
    await page.goto(route.path, { waitUntil: 'networkidle' });

    const results = await new AxeBuilder({ page })
      .withTags(WCAG_TAGS)
      // Exclude third-party widgets you do not control. Keep this list minimal.
      // .exclude('iframe[title="reCAPTCHA"]')
      .analyze();

    // Blocking set: critical + serious. Moderate and minor do not fail this test;
    // the review gate re-evaluates them from the JSON.
    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );

    if (blocking.length > 0) {
      // Compact summary so CI output shows the issue without noise.
      console.log(`\n[a11y] ${route.name} violations:`);
      for (const v of blocking) {
        console.log(`  - [${v.impact}] ${v.id}: ${v.help}`);
        console.log(`    nodes: ${v.nodes.length}, first: ${v.nodes[0]?.target?.join(' ')}`);
        console.log(`    wcag:  ${v.tags.filter((t) => t.startsWith('wcag')).join(', ')}`);
      }
    }

    expect(blocking, `${blocking.length} critical/serious a11y violations on ${route.path}`).toEqual([]);
  });
}
