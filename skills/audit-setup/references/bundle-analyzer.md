# Bundle analyzer snippets

/audit-setup never edits framework config files. Paste the matching snippet yourself.

## Next.js

```typescript
// next.config.ts - add the withBundleAnalyzer wrapper
import type { NextConfig } from 'next';
import bundleAnalyzer from '@next/bundle-analyzer';

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
});

const nextConfig: NextConfig = {
  // ...your existing config
};

export default withBundleAnalyzer(nextConfig);
```

If your config already ends with `export default nextConfig`, wrap it:
`export default withBundleAnalyzer(nextConfig);`. For `.js` and `.mjs` configs the shape is the
same: import `@next/bundle-analyzer` and wrap the config object before exporting.

Run the `analyze` script that /audit-setup added (`npm run analyze`, `pnpm analyze`,
`yarn analyze` or `bun run analyze`). It runs the build with `ANALYZE=true`.

The analyzer opens a tree map of every chunk. Look for:

- Unexpectedly large `node_modules/*` chunks (a whole utility library imported for one function)
- Client-side code that should be server-only
- Duplicate modules, often from polyfill mismatches

## Vite

```typescript
// vite.config.ts - add the visualizer to plugins
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    // ...your existing plugins
    visualizer({ filename: 'dist/stats.html', open: false, gzipSize: true }),
  ],
});
```

Then run the build and open `dist/stats.html`.
