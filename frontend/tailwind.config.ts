import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202d",
        canvas: "#f7f8fb",
        signal: "#2c6bed",
        mint: "#1db89b",
      },
      boxShadow: {
        panel: "0 16px 50px rgba(24, 39, 75, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
