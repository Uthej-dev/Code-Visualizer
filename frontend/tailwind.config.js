/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        ink: {
          950: '#080b12',
          900: '#0c111b',
          850: '#101623',
          800: '#151c2b',
          700: '#1e2738',
          600: '#2a3549',
          500: '#3b4760',
        },
      },
      keyframes: {
        flash: {
          '0%': { backgroundColor: 'rgba(56, 189, 248, 0.35)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'value-in': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'value-out': {
          '0%': { opacity: '1', transform: 'translateY(0)' },
          '100%': { opacity: '0', transform: 'translateY(-8px)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
      animation: {
        flash: 'flash 1.1s ease-out',
        'value-in': 'value-in 320ms ease-out both',
        'value-out': 'value-out 420ms ease-in forwards',
        'fade-in': 'fade-in 200ms ease-out both',
      },
    },
  },
  plugins: [],
};
