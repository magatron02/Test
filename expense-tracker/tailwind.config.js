/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        green:   "#3DED97",
        income:  "#3DED97",
        expense: "#FF6B6B",
        primary: "#3DED97",
        bg:      "#0D0D0D",
        surface: "#161616",
        card:    "#1C1C1C",
        card2:   "#222222",
        border:  "#2A2A2A",
        muted:   "#5A5A5A",
        sub:     "#888888",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        green:  "0 0 30px rgba(61,237,151,0.20)",
        green2: "0 0 60px rgba(61,237,151,0.12)",
      },
    },
  },
  plugins: [],
};
