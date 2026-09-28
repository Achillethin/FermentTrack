/** @type {import('tailwindcss').Config} */
// The app's markup uses Tailwind's `slate` (neutrals) and `emerald` (accent)
// names throughout. Redefining those two ramps here re-themes every component
// at once: slate becomes warm "stoneware", emerald becomes muted celadon.
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        slate: {
          50: "#f6f2ec",
          100: "#ebe5db",
          200: "#dcd3c5",
          300: "#c2b8a7",
          400: "#a89c8a",
          500: "#8a7f6f",
          600: "#6a6051",
          700: "#453e34",
          800: "#2f2a23",
          900: "#1e1a16",
          950: "#120f0c",
        },
        emerald: {
          50: "#f0faf5",
          100: "#d9f2e6",
          200: "#b4e4cf",
          300: "#8fd3b6",
          400: "#6fc4a2",
          500: "#4ea787",
          600: "#3a8a6d",
          700: "#2f7259",
          800: "#265b47",
          900: "#1e4738",
          950: "#0f2a21",
        },
        paper: "#dfd2b3",
        ink: "#2a2117",
      },
      fontFamily: {
        sans: ['"Atkinson Hyperlegible"', "system-ui", "sans-serif"],
        display: ['"Bricolage Grotesque"', '"Atkinson Hyperlegible"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
