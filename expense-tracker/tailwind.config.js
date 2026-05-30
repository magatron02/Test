/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        income: "#10b981",
        expense: "#ef4444",
        primary: "#6366f1",
        surface: "#1e1e2e",
        bg: "#13131f",
        card: "#252537",
        muted: "#6b7280",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
