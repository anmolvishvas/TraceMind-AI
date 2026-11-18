/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: "#090D16",
        surface: "#111827",
        elevated: "#1F2937",
        borderDark: "#374151",
        brandCyan: "#06B6D4",
        brandViolet: "#8B5CF6",
        critical: "#EF4444",
        high: "#F97316",
        medium: "#F59E0B",
        low: "#38BDF8",
        success: "#10B981",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
