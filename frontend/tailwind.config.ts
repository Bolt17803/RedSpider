import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'obsidian': '#050505',
        'carbon': '#111111',
        'carbon-light': '#1a1a1a',
        'platinum': '#e5e5e5',
        'platinum-muted': '#a3a3a3',
        'platinum-dark': '#525252',
        'gold-accent': '#d4af37',
        // Keeping legacy names mapped to new colors gracefully to prevent breakages
        'warm-dark': '#050505',
        'warm-darker': '#000000',
        'warm-gray': '#111111',
        'warm-beige': '#e5e5e5',
        'warm-amber': '#ffffff', // Mapped to stark white for a cleaner look
        'warm-orange': '#d4af37', // Mapped to gold accent
        'warm-coral': '#fd7f6f',
        'warm-purple': '#a78bfa',
        'warm-teal': '#14b8a6',
      },
      animation: {
        'pulse-soft': 'pulse-soft 4s ease-in-out infinite',
        'glow-platinum': 'glow-platinum 3s ease-in-out infinite alternate',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': {
            opacity: '1',
            transform: 'scale(1)',
          },
          '50%': {
            opacity: '0.9',
            transform: 'scale(1.02)',
          },
        },
        'glow-platinum': {
          '0%': {
            boxShadow: '0 0 10px rgba(229, 229, 229, 0.1), 0 0 20px rgba(229, 229, 229, 0.05)',
          },
          '100%': {
            boxShadow: '0 0 15px rgba(229, 229, 229, 0.2), 0 0 25px rgba(229, 229, 229, 0.1)',
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
export default config

