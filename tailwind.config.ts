import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        gold: {
          DEFAULT: '#D4A017',
          50: '#FBF3DB',
          100: '#F8E9BD',
          200: '#F1D682',
          300: '#EAC247',
          400: '#DEAD21',
          500: '#D4A017',
          600: '#A07912',
          700: '#6B510C',
          800: '#372907',
          900: '#1A1303',
        },
        emerald: {
          DEFAULT: '#10B981',
        },
        ink: {
          950: '#0A0A0A',
          900: '#0F0F0F',
          800: '#1A1A1A',
          700: '#242424',
          600: '#2F2F2F',
          500: '#3D3D3D',
          400: '#5A5A5A',
          300: '#8A8A8A',
          200: '#B5B5B5',
          100: '#E0E0E0',
          50: '#F5F5F5',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'gold-gradient': 'linear-gradient(135deg, #D4A017 0%, #F1D682 50%, #D4A017 100%)',
        'radial-gold': 'radial-gradient(circle at 50% 0%, rgba(212,160,23,0.25), transparent 60%)',
      },
      boxShadow: {
        gold: '0 10px 40px -10px rgba(212, 160, 23, 0.35)',
        'gold-lg': '0 20px 60px -10px rgba(212, 160, 23, 0.55)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 3s linear infinite',
        shimmer: 'shimmer 2.5s linear infinite',
        float: 'float 6s ease-in-out infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
      },
    },
  },
  plugins: [],
}
export default config
