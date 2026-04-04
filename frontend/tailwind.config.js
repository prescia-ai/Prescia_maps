/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'map-dark': '#1a1a2e',
        'map-panel': '#16213e',
        'map-accent': '#0f3460',
        'map-highlight': '#e94560',
      },
    },
  },
  plugins: [],
};
