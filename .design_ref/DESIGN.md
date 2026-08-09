---
name: Academic Ethereal
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#464555'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#777587'
  outline-variant: '#c7c4d8'
  surface-tint: '#4d44e3'
  primary: '#3525cd'
  on-primary: '#ffffff'
  primary-container: '#4f46e5'
  on-primary-container: '#dad7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#712ae2'
  on-secondary: '#ffffff'
  secondary-container: '#8a4cfc'
  on-secondary-container: '#fffbff'
  tertiary: '#003fac'
  on-tertiary: '#ffffff'
  tertiary-container: '#0555dd'
  on-tertiary-container: '#d1daff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3323cc'
  secondary-fixed: '#eaddff'
  secondary-fixed-dim: '#d2bbff'
  on-secondary-fixed: '#25005a'
  on-secondary-fixed-variant: '#5a00c6'
  tertiary-fixed: '#dbe1ff'
  tertiary-fixed-dim: '#b4c5ff'
  on-tertiary-fixed: '#00174b'
  on-tertiary-fixed-variant: '#003ea8'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  body-intro:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: -0.01em
  body-main:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: '0'
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
  mono-ui:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.4'
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1280px
  gutter: 24px
  margin-desktop: 48px
  margin-mobile: 20px
  stack-sm: 12px
  stack-md: 24px
  stack-lg: 48px
---

## Brand & Style
The design system centers on a "Premium Intelligence" narrative, blending the academic rigor of high-end universities with the cutting-edge fluidity of modern AI interfaces. The aesthetic is a hybrid of **Minimalism** and **Glassmorphism**, characterized by expansive negative space, translucent surfaces, and high-precision typography.

The interface should feel atmospheric and calm, reducing the cognitive load of complex admission processes. It evokes a sense of "digital concierge"—sophisticated, silent, and deeply capable. Key visual pillars include:
- **Optical Clarity:** High-contrast text on layered, translucent backgrounds.
- **Architectural Depth:** Using light and blur rather than heavy borders to define space.
- **Fluidity:** Soft transitions and rounded geometry that feel organic yet structured.

## Colors
The palette is rooted in **Deep Indigo** and **Royal Blue** to establish institutional trust, while **Vibrant Purple** serves as the "AI spark" for interactive elements and active states.

- **Primary (Indigo):** Used for primary actions and brand presence.
- **Secondary (Purple):** Reserved for AI-driven features, suggestions, and highlighting "smart" insights.
- **Tertiary (Royal Blue):** Used for links, informational icons, and secondary highlights.
- **Surface Strategy:** In Light Mode, use ultra-subtle off-white (#F8FAFC) backgrounds with pure white glass cards. In Dark Mode, use a deep navy-black (#020617) with semi-transparent charcoal overlays.

## Typography
The system utilizes **Inter** for its neutral, highly legible character, ensuring that dense admission data remains accessible. For technical or AI-generated metadata, **Geist** provides a modern, monospaced precision that distinguishes machine output from human-centric content.

- **Headlines:** Use tight letter-spacing and bold weights to create a sense of authority.
- **Body:** Prioritize line height (1.5x+) to maintain the "spacious" feel requested.
- **Contrast:** Use a secondary text color (60% opacity) for supporting descriptions to maintain the hierarchy.

## Layout & Spacing
The layout follows a **Fluid Grid** model with generous margins to evoke a "gallery" feel. 

- **Sidebar Navigation:** A fixed-width (280px) translucent sidebar on desktop, collapsing to a bottom-bar or drawer on mobile.
- **Content Alignment:** Center-aligned chat threads with a maximum width of 800px to optimize readability. 
- **Rhythm:** Use an 8px base unit. Component internal padding should be generous (typically 24px or 32px) to support the "clean and spacious" requirement.
- **Mobile Reflow:** Cards stack vertically with 16px margins, and typography scales down to prevent horizontal scrolling.

## Elevation & Depth
Depth is achieved through **Backdrop Blurs** and **Tonal Stacking** rather than traditional drop shadows.

1.  **Level 0 (Base):** Solid background color (Light or Dark).
2.  **Level 1 (Cards):** Translucent surface (10-20% opacity) with a 20px Backdrop Blur and a 1px white/light-gray inner stroke to simulate a glass edge.
3.  **Level 2 (Floating Elements):** Chat inputs and dropdowns use a soft, ultra-diffused shadow (0px 20px 50px rgba(0,0,0,0.1)) combined with the glass effect to appear "hovering."
4.  **Level 3 (Modals):** High-opacity glass with a darker background dim (60% opacity).

## Shapes
The shape language is overtly **Rounded**, signaling approachability and modern tech-forwardness.

- **Main Cards/Containers:** 24px corner radius.
- **Buttons & Inputs:** 12px or full-pill radius.
- **Avatars/Icons:** Circular or high-radius squircle.
- **Selection States:** Use subtle 8px rounded corners for focus rings to maintain consistency.

## Components
### Floating Chat Input
A pill-shaped container sitting at the bottom of the viewport. Use a high-degree glass blur, a subtle purple glow on focus, and an "Send" icon that transforms into a loading pulse when processing.

### Suggestion Cards
Horizontal-scrolling cards with 24px corners. Use a 1px gradient border (Indigo to Purple) to draw attention. Background should be 5% primary color with a light blur.

### Sidebar Navigation
Glass surface with no border on the right. Active items should use a subtle vertical pill indicator and a background tint (#4F46E5 at 10% opacity).

### Detailed Profile Forms
Input fields should be "Ghost" style—transparent backgrounds with a bottom border or subtle fill, transforming into a solid glass surface on focus. 

### Status Badges
Small, pill-shaped chips with low-saturation backgrounds (e.g., light blue for "In Progress," soft green for "Accepted") and bold, high-contrast labels using the `label-caps` typography style.