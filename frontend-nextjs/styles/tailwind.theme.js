// Add to tailwind.config.js theme.extend.colors
module.exports = {
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg-rgb) / <alpha-value>)",
        panel: "rgb(var(--panel-rgb) / <alpha-value>)",
        "panel-2": "rgb(var(--panel-2-rgb) / <alpha-value>)",
        border: "rgb(var(--border-rgb) / <alpha-value>)",
        text: "rgb(var(--text-rgb) / <alpha-value>)",
        "text-2": "rgb(var(--text-2-rgb) / <alpha-value>)",
        muted: "rgb(var(--muted-rgb) / <alpha-value>)",
        accent: "rgb(var(--accent-rgb) / <alpha-value>)",
        "accent-2": "rgb(var(--accent-2-rgb) / <alpha-value>)",
        success: "rgb(var(--success-rgb) / <alpha-value>)",
        warning: "rgb(var(--warning-rgb) / <alpha-value>)",
        danger: "rgb(var(--danger-rgb) / <alpha-value>)",
        hover: "rgb(var(--hover-rgb) / <alpha-value>)",
        active: "rgb(var(--active-rgb) / <alpha-value>)",
        focus: "rgb(var(--focus-rgb) / <alpha-value>)",
        disabled: "rgb(var(--disabled-rgb) / <alpha-value>)",
        ring: "rgb(var(--ring-rgb) / <alpha-value>)",
      },
      borderColor: {
        DEFAULT: "rgb(var(--border-rgb) / <alpha-value>)",
      },
      ringColor: {
        DEFAULT: "var(--ring)",
      },
      backgroundColor: {
        DEFAULT: "rgb(var(--bg-rgb) / <alpha-value>)",
      },
    },
  },
};
