import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{vue,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Palette custom horror
        'blood-red': {
          50: '#ffe5e5',
          100: '#ffcccc',
          200: '#ff9999',
          300: '#ff6666',
          400: '#ff3333',
          500: '#cc0000', // Principale - rouge sang
          600: '#990000',
          700: '#660000',
          800: '#330000',
          900: '#1a0000',
        },
        'deep-black': {
          50: '#f5f5f5',
          100: '#e0e0e0',
          200: '#c0c0c0',
          300: '#a0a0a0',
          400: '#606060',
          500: '#2a2a2a', // Principale - noir profond
          600: '#1f1f1f',
          700: '#151515',
          800: '#0a0a0a',
          900: '#000000',
        },
        'smoke-gray': {
          50: '#f9f9f9',
          100: '#f0f0f0',
          200: '#e0e0e0',
          300: '#c9c9c9',
          400: '#a0a0a0',
          500: '#7a7a7a', // Principale - gris fumée
          600: '#656565',
          700: '#505050',
          800: '#3a3a3a',
          900: '#252525',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}

export default config
