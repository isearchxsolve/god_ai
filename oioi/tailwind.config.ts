import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        // Background layers (z-axis depth)
        bg: {
          base: '#0a0a0b',
          surface: '#131316',
          elevated: '#1c1c21',
          canvas: '#0f0f12',
        },
        // Foreground
        fg: {
          primary: '#ededed',
          secondary: '#a1a1aa',
          muted: '#71717a',
          inverse: '#0a0a0b',
        },
        // Brand accent (violet→fuchsia)
        accent: {
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          glow: '#8b5cf633',
        },
        // Semantic
        success: '#22c55e',
        warning: '#f59e0b',
        danger: '#ef4444',
        info: '#3b82f6',
        // Borders
        border: {
          subtle: '#27272a',
          strong: '#3f3f46',
        },
        // Legacy alias kept for back-compat with any existing usage
        primary: {
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        sm: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      boxShadow: {
        elevated: '0 1px 2px #00000040, 0 8px 24px #00000060',
        glow: '0 0 0 4px #8b5cf633',
      },
      transitionTimingFunction: {
        canvas: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 0 0 #8b5cf633' },
          '50%': { boxShadow: '0 0 0 6px #8b5cf633' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s linear infinite',
        'pulse-glow': 'pulse-glow 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
