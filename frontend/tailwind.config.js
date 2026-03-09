/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        canvas:  '#F5F3EF',
        surface: {
          DEFAULT: '#FFFFFF',
          2: '#F0EDE8',
          3: '#E8E4DE',
        },
        border: {
          DEFAULT: '#D4CFC8',
          muted:   '#E4DED8',
        },
        ink: {
          DEFAULT: '#1C1C1E',
          2: '#4A4A4E',
          3: '#6A6A6E',
          4: '#9A9A9E',
        },
        teal: {
          DEFAULT: '#0D4F4F',
          light:   'rgba(13,79,79,0.07)',
          border:  'rgba(13,79,79,0.18)',
        },
        go: {
          DEFAULT: '#2D936C',
          light:   'rgba(45,147,108,0.08)',
          border:  'rgba(45,147,108,0.22)',
        },
        caution: {
          DEFAULT: '#D4930D',
          light:   'rgba(212,147,13,0.08)',
          border:  'rgba(212,147,13,0.22)',
        },
        nogo: {
          DEFAULT: '#C1292E',
          light:   'rgba(193,41,46,0.08)',
          border:  'rgba(193,41,46,0.22)',
        },
        gold: {
          DEFAULT: '#B8953E',
          light:   'rgba(184,149,62,0.08)',
          border:  'rgba(184,149,62,0.22)',
        },
      },
      boxShadow: {
        card:       '0 1px 3px rgba(28,28,30,0.08), 0 1px 2px rgba(28,28,30,0.04)',
        'card-md':  '0 4px 12px rgba(28,28,30,0.09), 0 2px 4px rgba(28,28,30,0.05)',
        verdict:    '0 0 50px rgba(0,0,0,0.05)',
      },
      animation: {
        'fade-in':  'fadeIn 0.35s ease-out forwards',
        'slide-up': 'slideUp 0.45s ease-out forwards',
        'pulse-dot': 'pulseDot 1.8s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:  { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        pulseDot: {
          '0%,100%': { opacity: '0.4', transform: 'scale(0.9)' },
          '50%':     { opacity: '1',   transform: 'scale(1.1)' },
        },
      },
    },
  },
  plugins: [],
}
