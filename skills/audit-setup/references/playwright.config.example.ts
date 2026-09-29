// playwright.config.ts - scaffolded by /audit-setup because none existed.
// Edit freely; the skill never overwrites an existing config.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
  },
  projects: [
    { name: 'a11y',  testMatch: /.*\.spec\.ts/, grep: /@a11y/ },
    { name: 'smoke', testMatch: /.*\.spec\.ts/, grepInvert: /@a11y/ },
  ],
});
