import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: "#2a78d6", // matches the extension icon brand color
      },
    },
  },
  plugins: [],
};

export default config;
