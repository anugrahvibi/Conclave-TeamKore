# Design Guidelines

## Styling & Layout

### UI Components
- **Main Box Corners**: The primary container elements use a "continuous squircle" style for their corners with a very large radius. This is achieved using the modern CSS `corner-shape: squircle` property combined with a substantial `border-radius` (`rounded-[4rem]` in Tailwind), providing a very smooth, Apple-like continuous curve compared to standard rounded rectangles.
- **Page Margin**: The outer wrapper utilizes a minimal, thin margin to maximize the container space while still maintaining a subtle floating effect (`p-1` on mobile, scaling to `p-2` on desktop).
