/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        groww: {
          green: '#00D09C',
          dark: '#0B1215',
          card: '#121B21',
          border: '#1F2D37',
          blue: '#5367FF',
        }
      }
    },
  },
  plugins: [],
}
