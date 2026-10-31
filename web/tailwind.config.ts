import typography from '@tailwindcss/typography';
import type { Config } from 'tailwindcss';
import animate from 'tailwindcss-animate';

/** A colour stored as RGB channels in globals.css, with opacity support. */
const rgb = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: ['class'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    // Class names that the game picks per party or per state.
    './lib/stimmts/**/*.ts',
  ],
  theme: {
    extend: {
      height: {
        'chat-header': 'var(--chat-header-height)',
        header: 'var(--header-height)',
        footer: 'var(--footer-height)',
      },
      minHeight: {
        'chat-header': 'var(--chat-header-height)',
      },
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        'chat-input': 'hsl(var(--chat-input))',
        ring: 'hsl(var(--ring))',
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
        // Stimmt's? (see globals.css). Vote colours live on seats and dots,
        // party colours only on bands and logo tiles, the tally tones only on
        // the player's Wahlperiode.
        'brand-red': rgb('brand-red'),
        seat: {
          yes: rgb('stimmts-seat-yes'),
          no: rgb('stimmts-seat-no'),
          abstain: rgb('stimmts-seat-abstain'),
          'absent-ring': rgb('stimmts-seat-absent-ring'),
          unaffiliated: rgb('stimmts-seat-unaffiliated'),
          pending: rgb('stimmts-seat-pending'),
        },
        tally: {
          low: rgb('tally-low'),
          mid: rgb('tally-mid'),
          top: rgb('tally-top'),
        },
        result: {
          correct: rgb('result-correct'),
          wrong: rgb('result-wrong'),
        },
        party: {
          linke: rgb('party-linke'),
          spd: rgb('party-spd'),
          gruene: rgb('party-gruene'),
          cdu: rgb('party-cdu'),
          afd: rgb('party-afd'),
        },
        paper: {
          DEFAULT: rgb('paper'),
          ink: rgb('paper-ink'),
          muted: rgb('paper-muted'),
          rule: rgb('paper-rule'),
        },
      },
      fontFamily: {
        // Set on the game's root by lib/stimmts/fonts.ts; the fallbacks keep
        // the metrics close when the variables are missing.
        display: ['var(--font-stimmts-display)', 'Arial', 'sans-serif'],
        document: [
          'var(--font-stimmts-document)',
          '"Times New Roman"',
          'Times',
          'serif',
        ],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        'typing-dot': {
          '0%, 60%, 100%': { transform: 'translateY(0)' },
          '30%': { transform: 'translateY(-4px)' },
        },
        // Stimmt's? (components/stimmts): screen changes, the waiting card's
        // ripple and hint, the cast into the urn, the reveal and the stamp.
        'stimmts-screen': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'none' },
        },
        'stimmts-pulse': {
          '0%': { opacity: '0.55', transform: 'scale(1)' },
          '100%': { opacity: '0', transform: 'scale(1.07)' },
        },
        'stimmts-hint': {
          '0%': { opacity: '0', transform: 'translateY(6px) scale(0.92)' },
          '8%, 82%': { opacity: '1', transform: 'none' },
          '100%': { opacity: '0', transform: 'translateY(-4px)' },
        },
        'stimmts-tap': {
          '0%, 100%': { transform: 'translateY(0) scale(1)' },
          '45%': { transform: 'translateY(-4px) scale(1)' },
          '60%': { transform: 'translateY(1px) scale(0.9)' },
        },
        // Casting, in three moves: fly, insert, fall. The flight's offset and
        // scale are measured into --dx, --dy and --s, so the card lands on the
        // slot wherever the layout puts the urn.
        'stimmts-fly': {
          '0%': { transform: 'none' },
          '30%': { transform: 'translateY(-12px) scale(0.96)' },
          '100%': {
            transform:
              'translate(var(--dx, 0px), var(--dy, 200px)) scale(var(--s, 0.12))',
          },
        },
        'stimmts-insert': {
          from: { transform: 'none' },
          to: { transform: 'translateY(32px)' },
        },
        'stimmts-fall': {
          '0%': { transform: 'translateY(var(--fall, -100px))' },
          '78%': { transform: 'translateY(0)' },
          '88%': { transform: 'translateY(-4px)' },
          '100%': { transform: 'translateY(0)' },
        },
        'stimmts-flip': {
          from: { opacity: '0', transform: 'rotateX(90deg) scale(0.9)' },
          to: { opacity: '1', transform: 'none' },
        },
        'stimmts-stamp': {
          from: { opacity: '0', transform: 'rotate(-6deg) scale(1.8)' },
          to: { opacity: '1', transform: 'rotate(-6deg) scale(1)' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'typing-dot': 'typing-dot 1.4s ease-in-out infinite',
        'stimmts-screen': 'stimmts-screen 0.25s ease both',
        'stimmts-pulse': 'stimmts-pulse 1.8s ease-out 1s infinite',
        'stimmts-hint': 'stimmts-hint 4.5s ease 0.9s both',
        'stimmts-tap': 'stimmts-tap 1.1s ease-in-out infinite',
        'stimmts-fly':
          'stimmts-fly 0.65s cubic-bezier(0.5, 0, 0.3, 1) forwards',
        'stimmts-insert':
          'stimmts-insert 0.38s cubic-bezier(0.5, 0, 1, 1) forwards',
        'stimmts-fall': 'stimmts-fall 0.6s cubic-bezier(0.55, 0, 1, 0.45) both',
        'stimmts-flip':
          'stimmts-flip 0.35s cubic-bezier(0.2, 1.4, 0.4, 1) both',
        'stimmts-stamp':
          'stimmts-stamp 0.45s cubic-bezier(0.2, 1.4, 0.4, 1) 0.25s both',
      },
    },
  },
  plugins: [animate, typography],
} satisfies Config;
