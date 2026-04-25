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
        // High-End Developer Theme
        'pure-black': '#000000',
        'charcoal-base': '#050505',
        'charcoal-surface': '#0A0A0B',
        'charcoal-elevated': '#121214',
        
        // Crisp Text
        'text-primary': '#FFFFFF',
        'text-secondary': '#A1A1AA', // Zinc 400
        'text-tertiary': '#71717A',  // Zinc 500
        
        // Accents
        'accent-indigo': '#6366F1',  // Indigo 500
        'accent-violet': '#8B5CF6',  // Violet 500
        'accent-silver': '#E4E4E7',  // Zinc 200
        'accent-glow': 'rgba(99, 102, 241, 0.15)', // Subtle indigo glow
        
        // Borders
        'border-subtle': 'rgba(255, 255, 255, 0.06)',
        'border-focus': 'rgba(255, 255, 255, 0.15)',
        
        // Legacy mappings (to prevent immediate breakage of missing classes before we replace them in components, though we will rewrite most)
        'obsidian': '#000000',
        'carbon': '#0A0A0B',
        'carbon-light': '#121214',
        'platinum': '#FFFFFF',
        'platinum-muted': '#A1A1AA',
        'platinum-dark': '#71717A',
        'gold-accent': '#6366F1',
        'electric-blue': '#8B5CF6',
        'electric-cyan': '#A855F7',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'premium-glass': 'linear-gradient(145deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)',
        'gradient-metallic': 'linear-gradient(135deg, #FFF 0%, #A1A1AA 100%)',
      },
      fontFamily: {
        heading: ['var(--font-outfit)', 'sans-serif'],
        sans: ['var(--font-manrope)', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'monospace'],
      },
      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'in-out-expo': 'cubic-bezier(0.87, 0, 0.13, 1)',
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-subtle': 'pulse-subtle 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-border': 'pulse-border 3s ease-in-out infinite',
        'spotlight': 'spotlight 10s ease-in-out infinite alternate',
        'mesh-1': 'mesh-1 20s ease-in-out infinite',
        'mesh-2': 'mesh-2 25s ease-in-out infinite alternate',
        'mesh-3': 'mesh-3 30s ease-in-out infinite',
      },
      keyframes: {
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(12px) filter(blur(4px))' },
          '100%': { opacity: '1', transform: 'translateY(0) filter(blur(0))' },
        },
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        'pulse-border': {
          '0%, 100%': { borderColor: 'rgba(255, 255, 255, 0.05)' },
          '50%': { borderColor: 'rgba(255, 255, 255, 0.15)' },
        },
        spotlight: {
          '0%': { opacity: '0.4', transform: 'translate(-5%, -5%) scale(1)' },
          '100%': { opacity: '0.7', transform: 'translate(5%, 5%) scale(1.05)' },
        },
        'mesh-1': {
          '0%': { transform: 'translate(0px, 0px) scale(1)' },
          '33%': { transform: 'translate(30px, -50px) scale(1.1)' },
          '66%': { transform: 'translate(-20px, 20px) scale(0.9)' },
          '100%': { transform: 'translate(0px, 0px) scale(1)' },
        },
        'mesh-2': {
          '0%': { transform: 'translate(0px, 0px) scale(1)' },
          '50%': { transform: 'translate(-40px, 30px) scale(1.05)' },
          '100%': { transform: 'translate(20px, -20px) scale(0.95)' },
        },
        'mesh-3': {
          '0%': { transform: 'translate(0px, 0px) scale(1)' },
          '33%': { transform: 'translate(-30px, 40px) scale(1.15)' },
          '66%': { transform: 'translate(20px, -30px) scale(0.85)' },
          '100%': { transform: 'translate(0px, 0px) scale(1)' },
        }
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
export default config

