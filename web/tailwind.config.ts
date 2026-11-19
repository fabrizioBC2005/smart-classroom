import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // misma paleta que la presentacion
        ink: '#13272E',
        deep: '#0B3C49',
        teal: '#028090',
        sea: '#00A896',
        amber: '#D98324',
        danger: '#C0392B',
        mist: '#F1F6F6',
        line: '#DDE7E8',
        muted: '#5C7178',
        page: '#F7FAFA',
      },
      boxShadow: {
        card: '0 1px 2px rgba(19,39,46,.04), 0 2px 8px -2px rgba(19,39,46,.06)',
        lift: '0 2px 4px rgba(19,39,46,.05), 0 12px 24px -8px rgba(19,39,46,.14)',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
export default config;
