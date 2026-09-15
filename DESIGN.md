# Design Guidelines

## Styling & Layout

### UI Components
- **Main Box Corners**: The primary container elements use a "continuous squircle" style for their corners with a very large radius. This is achieved using the modern CSS `corner-shape: squircle` property combined with a substantial `border-radius` (`rounded-[4rem]` in Tailwind), providing a very smooth, Apple-like continuous curve compared to standard rounded rectangles.
- **Page Margin**: The outer wrapper utilizes a minimal, thin margin to maximize the container space while still maintaining a subtle floating effect (`p-1` on mobile, scaling to `p-2` on desktop).
- **Scrollbars**: Use custom minimal scrollbars throughout the application. They should be thin (6px), with a transparent track and a subtle light-gray thumb (`#cbd5e1`) with fully rounded corners, avoiding default heavy or thick scrollbar styling.

### Corner Rounding (Nested & Generous)
- **Never 0 Rounding**: Every visible component, control, and surface must have rounded corners. Sharp (0-radius) elements are prohibited.
- **Nested (Concentric) Rounding**: Parent roundness = inner roundness + padding. A rounded parent's radius must equal its child's radius plus the padding between them (`parent radius = child radius + padding`, equivalently `child radius = parent radius − parent padding`). Keep the curves concentric (iOS-style); never mix arbitrary radii that break the nesting.
- **Err Generous**: When picking a radius, round up — a bit of excessive rounding is preferred. The main map box (`rounded-[4rem]` + `corner-shape: squircle`) is the reference example; keep it unchanged.
- **Chips & Pills**: Small chips, badges, tags, and the search pill always use full rounding (`border-radius: 9999px`).
- **Edge-Flush Exception**: Elements flush against a container edge (e.g. map attribution) may keep square corners only on the edge they touch.
- **Third-Party Surfaces**: Override bundled-library chrome (MapLibre popups, close buttons, attribution) in `globals.css` so third-party components follow these rounding rules too.

### Styling Restrictions (Strict)
- **No Double Outlines**: Never stack an outline on top of a border (or two decorative outlines on one element). An element gets a single border at most; use filled background/opacity changes for selection states instead of nested outline rings.
- **No Glow**: No glowing effects of any kind — no `box-shadow` spread with a bright color (e.g. `0 0 10px ...`), no `text-shadow` halos, no `filter: drop-shadow` glows, no luminous highlight rings.
- **No Gradients**: Never use `linear-gradient`, `radial-gradient`, or CSS `gradient()` values for backgrounds, overlays, or icon scrims — including gradient overlays on imagery (e.g. basemap preview tiles).
- **No Dark Components**: No dark-surface UI chrome. Components must stay light: white/`#f8fafc`-family surfaces with slate text. No dark scrim backgrounds (e.g. `rgba(15,23,42,...)`, `#020617`), no dark translucent panels with `backdrop-blur`, no dark text-shadow for label readability.
  - *Exception*: The map container that sits directly behind the 3D globe stays dark (`bg-slate-950`) — the globe renders against space, and a white backdrop would wash out the atmosphere and horizon.
- **No Shadow**: No `box-shadow` or `text-shadow` at all. Depth is conveyed with 1px borders on light surfaces only (`#e2e8f0`-family).
- **Selection & Emphasis**: Selection state = solid 2px `#0284c7` border + no outline ring; emphasis = solid fills, not shadows or gradients.

## Map Styling
- **Map surfaces**: Terrain, hillshade and sky colors must also stay in the light palette (no near-black shadow/horizon colors like `#020617`).

## Iconography & Assets

- **Phosphor Icons**: Only Phosphor icons (`@phosphor-icons/react`) must be used for UI icons, basemap indicators, search suggestions, map popups, and shortcut guides. Emojis are strictly prohibited throughout the application.
