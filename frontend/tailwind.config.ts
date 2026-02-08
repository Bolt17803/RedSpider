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
        'warm-dark': '#1a1715',
        'warm-darker': '#141210',
        'warm-gray': '#2a2522',
        'warm-beige': '#f5ebe0',
        'warm-amber': '#f59e0b',
        'warm-orange': '#fb923c',
        'warm-coral': '#fd7f6f',
        'warm-purple': '#a78bfa',
        'warm-teal': '#14b8a6',
      },
      animation: {
        'pulse-soft': 'pulse-soft 3s ease-in-out infinite',
        'glow-warm': 'glow-warm 2s ease-in-out infinite alternate',
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
        'glow-warm': {
          '0%': {
            boxShadow: '0 0 10px rgba(245, 158, 11, 0.3), 0 0 20px rgba(245, 158, 11, 0.2)',
          },
          '100%': {
            boxShadow: '0 0 20px rgba(245, 158, 11, 0.5), 0 0 30px rgba(245, 158, 11, 0.3)',
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

