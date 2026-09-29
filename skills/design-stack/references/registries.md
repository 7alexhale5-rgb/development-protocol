# Component registries

Eight public registries publish shadcn-format JSON. Wire them into a project's `components.json` once, then install components with `npx shadcn add`. All are free; none needs an account.

## components.json Template

Add the `registries` block to the project's `components.json` (adjust `tailwind` and `aliases` to the project):

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "zinc",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "registries": {
    "@shadcn":    "https://ui.shadcn.com/r/{name}.json",
    "@magicui":   "https://magicui.design/r/{name}.json",
    "@origin":    "https://originui.com/r/{name}.json",
    "@cult":      "https://cult-ui.com/r/{name}.json",
    "@animate":   "https://animate-ui.com/r/{name}.json",
    "@aceternity":"https://ui.aceternity.com/registry/{name}.json",
    "@motion":    "https://motion-primitives.com/c/{name}.json",
    "@21st":      "https://21st.dev/r/{name}"
  }
}
```

## Usage

```bash
# shadcn base primitive
npx shadcn add @shadcn/button

# Cult UI AI chat component
npx shadcn add @cult/ai-chat

# 21st.dev community component
npx shadcn add @21st/author-slug/component-slug

# Magic UI animated beam
npx shadcn add @magicui/animated-beam

# Aceternity hero card
npx shadcn add @aceternity/3d-card

# Motion Primitives morph dialog
npx shadcn add @motion/morph-dialog

# Origin UI data table
npx shadcn add @origin/data-table

# Animate UI menu
npx shadcn add @animate/menu
```

## When to use which registry

| Building | Check in order |
|---|---|
| **Dashboard / app UI** | `@shadcn`, then `@cult`, then `@origin`, then `@21st` |
| **Landing page** | `@aceternity`, then `@magicui`, then `@21st` |
| **Chat / AI UI** | `@cult` (AI-first patterns), then `@21st`, then `@shadcn` |
| **Animated hero** | `@aceternity`, then `@magicui`, then `@motion` |
| **Data tables** | `@shadcn`, then `@origin` |
| **Forms** | `@shadcn`, then `@origin` |
| **Micro-interactions** | `@motion`, then `@animate`, then `@magicui` |
| **Marketing sections** | `@aceternity`, then `@21st` |
| **Premium/dark aesthetic** | `@cult`, then `@aceternity` |

## Sites without a registry endpoint

Some component sites (for example hover.dev, Eldora UI, Syntax UI) publish no registry JSON. Browse
them with browser automation when needed, copy the component source by hand, and record the source
URL and license in the Step 9 report.

## Registry health check

Registries move. Before relying on one, probe it:

```sh
for u in \
  https://ui.shadcn.com/r/button.json \
  https://magicui.design/r/animated-beam.json \
  https://originui.com/r/button-01.json \
  https://cult-ui.com/r/ai-chat.json \
  https://animate-ui.com/r/menu.json \
  https://ui.aceternity.com/registry/3d-card.json \
  https://motion-primitives.com/c/morph-dialog.json; do
  printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "$u")" "$u"
done
```

A steady 404 or 500 means the endpoint moved: update the template above before using it.

## How /design-stack uses this list

- Step 4 (reference scan): browse matching components across registries.
- Step 6 `--generate`: `npx shadcn add @registry/name` for the user's pick or the brief's choice.

## Adding a registry

1. Confirm it publishes shadcn-format JSON at a stable path.
2. Add it to the `registries` map above.
3. Add a row to the "when to use which" table.
4. Add its probe URL to the health check.
