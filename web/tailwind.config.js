/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:      "#0A0E1A",
        surface: "#131827",
        card:    "#1A2235",
        border:  "#252D40",
        primary: "#3B82F6",
        accent:  "#8B5CF6",
        success: "#10B981",
        danger:  "#EF4444",
        warning: "#F59E0B",
        muted:   "#64748B",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
