# Website Theme: Fantasy Sports AI Assistant

This rule defines the design language for the frontend. Apply these guidelines when creating or modifying UI components, pages, or styles.

## Current State

The site uses plain CSS with CSS custom properties, no framework. All styles are in `app.css` (global tokens) and scoped `<style>` blocks in Svelte components.

## Design Philosophy

The site should feel like a **modern fantasy sports platform** (Sleeper, DraftKings, ESPN Fantasy) — not a generic SaaS landing page. Sports fans expect energy, confidence, and data density. Every design decision should ask: "Does this feel like a sports platform or a tech startup?"

---

## Color Palette

Replace the current generic blue/cyan palette with a sports-forward dark theme.

### Base Colors
- **Background**: Deep navy `#05091D` (not gray, not pure black — inspired by Sleeper's "Black Pearl")
- **Surface / Cards**: `#0F1628` — slightly elevated from the background
- **Elevated Surface**: `#1A2338` — for modals, dropdowns, hover states
- **Border**: `#1E2D4A` — subtle, blue-tinted borders

### Accent Colors
- **Primary Accent**: Electric cyan `#00E5FF` — the signature color. Use for CTAs, key stats, active states, links
- **Secondary Accent**: Vivid green `#00FF88` — use sparingly for positive indicators (up trends, "start" recommendations, success states)
- **Warning/Watch**: Amber `#FFB800` — caution, injury alerts, "risky" indicators
- **Negative**: Red `#FF4757` — down trends, "sit" recommendations, errors

### Text Colors
- **Primary Text**: `#E8EDF5` — high contrast on dark backgrounds
- **Secondary Text**: `#8899B0` — muted labels, supporting info
- **Accent Text**: Use `#00E5FF` for interactive text, links, and emphasis

### Semantic Color Rules
- Green = positive / go / start / up trend
- Red = negative / stop / sit / down trend
- Amber = caution / watch / injury / uncertain
- Cyan = interactive / action / AI insight

---

## Typography

Sports typography conveys energy and authority. Use condensed bold fonts for impact and clean sans-serifs for readability.

### Font Stack
- **Headlines / Display**: `'Barlow Condensed', 'Inter Tight', sans-serif` — weight 700-800, uppercase with `letter-spacing: 0.04em`
- **Body**: `'Inter', -apple-system, BlinkMacSystemFont, sans-serif` — weight 400-500
- **Stats / Numbers**: `'Inter', sans-serif` with `font-variant-numeric: tabular-nums` and weight 700
- **Labels / Tags**: `'Inter', sans-serif` — uppercase, weight 600, `letter-spacing: 0.06em`, small size

### Type Scale
- Hero headline: `3.5rem` (mobile: `2.25rem`), condensed bold, uppercase
- Section heading: `2rem` (mobile: `1.5rem`), condensed bold, uppercase
- Card title: `1.25rem`, weight 600
- Body: `1rem`, line-height 1.6
- Stat number (large): `2.5rem`+, weight 700, tabular nums
- Label: `0.75rem`, uppercase, letter-spacing `0.06em`

### Typography Rules
- Headlines should be **ALL CAPS** with condensed font — this is a universal sports pattern
- Stat numbers should be **large and bold** — make projections and scores visually dominant
- Use **extreme size contrast** between headlines and body text for drama
- Labels and categories (position tags like QB/WR/RB, status badges) should be small uppercase

---

## Layout Patterns

### Information Density
Sports fans expect **higher information density** than typical SaaS. Resist excessive whitespace. Pack meaningful data into visible space while maintaining clear visual hierarchy.

### Card-Based Design
Cards are the atomic unit of sports UI. Use them for:
- AI insights / recommendations
- Player mentions with stats
- Feature descriptions
- Blog post previews

Card style:
- Background: surface color with 1px border
- Border-radius: `0.5rem`
- Padding: `1.25rem`
- Subtle hover: border shifts to cyan, slight lift via `translateY(-2px)` + shadow

### Visual Hierarchy Within Cards
1. **Primary number/headline** — largest, boldest element
2. **Name/title** — medium weight
3. **Supporting context** — smallest, muted color, often with color-coded indicators

### Section Dividers
Use **diagonal clip-paths or angled dividers** (2-3 degrees) between major page sections to break the horizontal SaaS grid. This injects athletic energy without being distracting.

```css
.section-divider {
  clip-path: polygon(0 0, 100% 2%, 100% 100%, 0 98%);
}
```

### Responsive Approach
- Desktop: max-width `1200px`, card grids with varied sizes
- Tablet (768px): stack to fewer columns, maintain density
- Mobile (480px): single column, reduce type scale, keep cards compact

---

## Visual Elements

### Ambient Glow
Add subtle radial gradient "spotlights" behind hero sections and key content areas. Dark backgrounds should feel like a **stadium at night** — dramatic lighting, not flat emptiness.

```css
.hero::before {
  background: radial-gradient(ellipse at 50% 0%, rgba(0, 229, 255, 0.08) 0%, transparent 60%);
}
```

### Diagonal / Angular Elements
- Use angled clip-paths on section backgrounds
- Diagonal lines in decorative elements (borders, dividers)
- Skewed background shapes behind feature sections
- Even 2-3 degrees of angle breaks the "SaaS grid" and reads as athletic

### Gradient Text
Use gradient text for hero headlines — cyan to white or cyan to green. This is a signature sports-tech look.

```css
.hero-title {
  background: linear-gradient(135deg, #00E5FF 0%, #E8EDF5 60%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

### Live / Fresh Indicators
Include pulsing indicators to create an "always live" feeling:
- Pulsing dot next to "live" or "updated" labels
- Subtle glow animation on fresh data
- "Updated Xm ago" timestamps with a pulse animation

```css
.pulse {
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### Color-Coded Trend Indicators
Use arrows and color to show direction at a glance:
- Green up arrow for positive trends
- Red down arrow for negative trends
- Amber dash for neutral/uncertain

---

## Motion & Animation

### Core Principles
- **Fast transitions**: 150-250ms with `ease-out` — sports feels fast, not floaty
- **Purposeful only**: every animation communicates a state change or data update
- **Always respect** `prefers-reduced-motion`

### Signature Animations
- **Number counters**: Animate stat numbers counting up to their value on load — this is the most "sports-feeling" micro-interaction
- **Card entrance**: Staggered fade-in from bottom (50ms delay between cards)
- **Highlight flash**: When data changes, briefly flash the cell background cyan then fade back
- **Hover lift**: Cards translate up 2px with a subtle shadow on hover

### What to Avoid
- Slow, elastic animations (these feel like lifestyle/wellness apps)
- Decorative animations with no informational purpose
- Any animation longer than 300ms for UI state changes (reserve 500-800ms for celebratory moments only)

---

## Component Patterns

### Buttons
- **Primary CTA**: Cyan background `#00E5FF`, dark text, bold weight. Strong and confident — "Draft Now", "Get Started", "Ask Gordie"
- **Secondary**: Transparent with cyan border
- **Active/press**: `scale(0.98)` with quick transition
- Border-radius: `0.375rem` (slightly less rounded than generic SaaS — sharper = sportier)

### Navigation
- Sticky header with `backdrop-filter: blur(12px)` on the navy background
- Keep nav items minimal — sports fans want content, not menus
- Active state: cyan underline or text color

### Badges / Tags
- Position labels (QB, WR, RB): small uppercase, distinct background colors per position
- Status badges: color-coded backgrounds (green/amber/red) with dark text
- Border-radius: `0.25rem` (pill shapes feel less sporty — keep them slightly angular)

### Hero Sections
- Full-width dark background with ambient cyan glow
- Massive condensed uppercase headline with gradient text
- Supporting text in muted color
- Strong CTA button with clear action verb

---

## What to Avoid

- **Generic SaaS patterns**: Excessive whitespace, muted pastels, rounded pill buttons, illustration-heavy sections, passive CTAs ("Learn More")
- **Purple/indigo accent colors**: These read as "tech startup", not "sports"
- **Rounded, friendly fonts**: These read as "kids app" or "wellness brand"
- **Uniform grid layouts**: Vary card sizes for visual rhythm. Featured content gets bigger cards.
- **Slow, bouncy animations**: Keep motion fast and purposeful
- **Low information density**: Sports fans want data. Don't hide it behind clicks.
- **Stock illustrations or abstract blobs**: Use bold typography and data as the visual elements instead

---

## Reference Platforms

When in doubt, reference these for visual direction:
- **Sleeper** — neon-on-dark aesthetic, gaming-meets-sports energy
- **DraftKings** — bold accent colors on dark, high data density
- **ESPN Fantasy (2025)** — card-based modular layout, player card patterns
- **Nike** — dramatic scale, bold typography, black staging, confident simplicity
