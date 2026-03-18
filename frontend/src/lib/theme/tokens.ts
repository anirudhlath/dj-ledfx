/**
 * dj-ledfx Design Tokens — Studio Hardware theme
 * Dark, hardware-inspired aesthetic for DJ performance control.
 */

export const colors = {
  // Background layers
  bg: {
    base: '#0a0a0a',
    surface: '#141414',
    elevated: '#1e1e1e',
    overlay: '#282828',
  },
  // Text
  text: {
    primary: '#e0e0e0',
    secondary: '#808080',
    muted: '#505050',
    accent: '#00e5ff',
  },
  // Accent / brand
  accent: {
    cyan: '#00e5ff',
    cyanDim: '#00b8cc',
    cyanGlow: 'rgba(0, 229, 255, 0.3)',
  },
  // Semantic
  status: {
    ok: '#00e676',
    okGlow: 'rgba(0, 230, 118, 0.3)',
    warning: '#ffab00',
    warningGlow: 'rgba(255, 171, 0, 0.3)',
    error: '#ff1744',
    errorGlow: 'rgba(255, 23, 68, 0.3)',
    offline: '#505050',
  },
  // Surface borders
  border: {
    subtle: '#2a2a2a',
    medium: '#3a3a3a',
    accent: '#00e5ff',
  },
} as const;

export const typography = {
  mono: "'JetBrains Mono', 'Fira Code', monospace",
  sans: "'Inter', system-ui, sans-serif",
  sizes: {
    bpmDisplay: '3rem',    // 48px
    heading: '1.25rem',    // 20px
    body: '0.875rem',      // 14px
    label: '0.75rem',      // 12px
    micro: '0.625rem',     // 10px
  },
} as const;

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  xxl: '32px',
} as const;

export const animation = {
  fast: '150ms',
  normal: '300ms',
  slow: '500ms',
  easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
} as const;
