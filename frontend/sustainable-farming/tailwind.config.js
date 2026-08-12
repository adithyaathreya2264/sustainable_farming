/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#2E7D32",
          dark: "#1B5E20",
          light: "#66BB6A",
        },
        danger: {
          DEFAULT: "#D32F2F",
          light: "#EF5350",
        },
        info: {
          DEFAULT: "#1976D2",
          light: "#42A5F5",
        },
        background: "#F5F5F5",
        surface: "#FFFFFF",
        ink: {
          DEFAULT: "#1A1A1A",
          muted: "#5F6B5F",
        },
        border: "#E0E0E0",
      },
      fontSize: {
        base: "16px",
      },
    },
  },
  plugins: [],
};
