# Design System: Behavior Lab

## 1. Visual Theme & Atmosphere
A quiet editorial laboratory. Balanced density (5), asymmetric composition (6), restrained fluid motion (4). The clickable phone is the visual anchor; adjacent evidence panels explain each action.

## 2. Color Palette & Roles
- Canvas #F7F8F9: page background.
- White #FFFFFF: phone and raised panels.
- Charcoal #24282B: primary text.
- Muted #667074: supporting text.
- Border #E0E5E4: structural separation.
- Teal #28766C: the single interaction and signal accent.

## 3. Typography Rules
Avenir Next, Avenir, sans-serif; native monospace for event records and scores. Display uses tight tracking and a controlled 30–49px scale. No serif or Inter. Compact labels are secondary; article body is 14px with 1.8 leading.

## 4. Component Stylings
Phone is a framed, independently scrollable experience. Panels use 12px corners and thin borders. Buttons have visible keyboard focus and tactile press feedback. Empty states explain the next useful action. CSS illustrations are bundled with no network dependencies.

## 5. Layout Principles
Maximum width 1440px. Desktop asymmetric phone/data split; below 768px, one column. No horizontal viewport overflow. 44px minimum interactive buttons. Phone navigation stays visible while the content scrolls.

## 6. Motion & Interaction
Brief transform/opacity feedback illustrates the already-completed event processing. Respect reduced-motion. Avoid continuous movement distracting from evidence.

## 7. Anti-Patterns
No neon, purple glows, generic serif, emoji illustrations, overlapping text, three equal feature cards, fake metrics or fabricated certainty. No personality conclusions from clicks.


## Expanded four-page experience

The landing page uses an asymmetric editorial hero: a left-aligned promise and a phone/cursor visualization on a pale dotted field. The conceptual swarm uses 30 bounded SVG cursor nodes animated with WAAPI transforms and opacity. It illustrates scale, never claims measured audience traffic. The natural user pointer stays unchanged. Pause, reduced-motion, offscreen and hidden-tab states control the animation. Illustrative counters update at a low frequency; they do not write backend events.

All pages share one navigation and footer. Architecture uses a vertical four-step guide on desktop; phones use a single-column layout. Tables scroll inside their bounded containers. Insights use nonexclusive topic counts, inspectable evidence and explicitly labeled scenario controls. Microcopy states current transport honestly. Data labels use monospace only where it helps inspection.

Use #F7F9F7 for the canvas, #243630 for primary text, #28766C for interaction emphasis and #DFE6DF for structure. Muted greens distinguish decorative cursor representatives; product actions retain a consistent accent. UI transitions use 150–200ms with cubic-bezier(.23,1,.32,1). Swarm choreography is explanatory marketing motion with longer cycles. Never animate layout dimensions or use a million DOM nodes.
