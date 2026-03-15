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
        // Deep Space Base (Luxurious Dark)
        'obsidian': '#030305',
        'carbon': '#08080C',
        'carbon-light': '#12121A',
        
        // Premium Text
        'platinum': '#F8F9FA',
        'platinum-muted': '#A1A1AA',
        'platinum-dark': '#52525B',
        
        // Accents
        'gold-accent': '#D4AF37',
        'gold-light': '#FCE69B',
        'electric-blue': '#3B82F6',
        'electric-cyan': '#06B6D4',

        // Legacy mappings
        'warm-dark': '#030305',
        'warm-darker': '#000000',
        'warm-gray': '#08080C',
        'warm-beige': '#F8F9FA',
        'warm-amber': '#ffffff',
        'warm-orange': '#D4AF37',
        'warm-coral': '#fd7f6f',
        'warm-purple': '#8B5CF6',
        'warm-teal': '#14b8a6',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'premium-glass': 'linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%)',
      },
      animation: {
        'pulse-soft': 'pulse-soft 4s ease-in-out infinite',
        'glow-platinum': 'glow-platinum 3s ease-in-out infinite alternate',
        'float-slow': 'float-slow 8s ease-in-out infinite',
        'float-slower': 'float-slow 12s ease-in-out infinite reverse',
        'aurora': 'aurora 20s linear infinite',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.9', transform: 'scale(1.02)' },
        },
        'glow-platinum': {
          '0%': { boxShadow: '0 0 10px rgba(229, 229, 229, 0.1), 0 0 20px rgba(229, 229, 229, 0.05)' },
          '100%': { boxShadow: '0 0 15px rgba(229, 229, 229, 0.2), 0 0 25px rgba(229, 229, 229, 0.1)' },
        },
        'float-slow': {
          '0%, 100%': { transform: 'translateY(0) translateX(0)' },
          '33%': { transform: 'translateY(-20px) translateX(10px)' },
          '66%': { transform: 'translateY(10px) translateX(-15px)' },
        },
        'aurora': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        }
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
export default config

