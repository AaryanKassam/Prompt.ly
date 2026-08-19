import type { Config } from "tailwindcss";

/**
 * Design tokens for Prompt.ly — "Modern Dark", the style the ui-ux-pro-max
 * database recommends for developer tools and analytics dashboards.
 *
 * Every colour is a semantic token so components never carry raw hex. The
 * surface ramp is deliberately shallow because dense dashboards read better
 * with low-contrast elevation and a single saturated accent.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces, darkest to lightest. Never pure #000 (OLED smear).
        canvas: "#0B1120",
        surface: {
          DEFAULT: "#0F172A",
          raised: "#151E33",
          overlay: "#1E293B",
          hover: "#233047",
        },
        line: {
          DEFAULT: "#1F2A3F",
          strong: "#2E3B54",
        },
        content: {
          DEFAULT: "#F8FAFC",
          muted: "#94A3B8",
          subtle: "#64748B",
          faint: "#475569",
        },
        // Single saturated accent — "code dark + run green".
        accent: {
          DEFAULT: "#22C55E",
          hover: "#16A34A",
          soft: "rgba(34, 197, 94, 0.12)",
          ring: "rgba(34, 197, 94, 0.35)",
        },
        // Score scale, shared by badges, bars and meters so a 6.4 always
        // looks the same wherever it appears.
        score: {
          low: "#EF4444",
          mid: "#F59E0B",
          high: "#22C55E",
        },
      },
      fontFamily: {
        sans: ["var(--font-fira-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-fira-code)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "0.625rem",
        xl: "0.875rem",
      },
      boxShadow: {
        raised: "0 1px 2px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.03) inset",
        glow: "0 0 0 1px rgba(34,197,94,0.35), 0 0 24px -6px rgba(34,197,94,0.35)",
      },
      transitionTimingFunction: {
        // Expo.out — the easing this style pairs with.
        expo: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "bar-grow": {
          from: { transform: "scaleX(0)" },
          to: { transform: "scaleX(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s cubic-bezier(0.16, 1, 0.3, 1) both",
        "bar-grow": "bar-grow 0.5s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
    },
  },
  plugins: [],
};

export default config;
