/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        // Bahra Electric Industrial Color Palette
        // Based on bahra-electric.com website - Red accent theme
        brand: {
          primary: "#32373c",
          "primary-dark": "#1a1f24",
          "primary-light": "#474d52",
          accent: "#cf2e2e",
          "accent-dark": "#a82424",
          "accent-light": "#e85555",
          success: "#00d084",
          warning: "#fcb900",
          orange: "#ff6900",
          danger: "#cf2e2e",
          purple: "#9b51e0",
          muted: "#abb8c3",
          red: "#cf2e2e",
          "red-dark": "#a82424",
          "red-light": "#e85555",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        success: {
          DEFAULT: "#00d084",
          foreground: "#ffffff",
        },
        warning: {
          DEFAULT: "#fcb900",
          foreground: "#1a1f24",
        },
        info: {
          DEFAULT: "#cf2e2e",
          foreground: "#ffffff",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.8)", opacity: "1" },
          "100%": { transform: "scale(1.5)", opacity: "0" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "pulse-ring": "pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "slide-up": "slide-up 0.3s ease-out",
        "fade-in": "fade-in 0.2s ease-out",
      },
      boxShadow: {
        "industrial": "0 4px 20px rgba(50, 55, 60, 0.08)",
        "industrial-hover": "0 8px 30px rgba(207, 46, 46, 0.15)",
        "red-glow": "0 0 20px rgba(207, 46, 46, 0.3)",
        "success-glow": "0 0 20px rgba(0, 208, 132, 0.3)",
      },
      backgroundImage: {
        "industrial-gradient": "linear-gradient(135deg, #1a1f24 0%, #32373c 100%)",
        "red-gradient": "linear-gradient(135deg, #cf2e2e 0%, #a82424 100%)",
        "accent-gradient": "linear-gradient(135deg, #cf2e2e 0%, #a82424 100%)",
        "success-gradient": "linear-gradient(135deg, #00d084 0%, #00a868 100%)",
        "warning-gradient": "linear-gradient(135deg, #fcb900 0%, #ff6900 100%)",
        "danger-gradient": "linear-gradient(135deg, #cf2e2e 0%, #a82424 100%)",
        "purple-gradient": "linear-gradient(135deg, #9b51e0 0%, #7b3eb0 100%)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
