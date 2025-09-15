/** @type {import('tailwindcss').Config} */
export default {
  theme: {
    extend: {
      colors: {},
    },
  },
  corePlugins: {
    preflight: false, // Disable Tailwind's reset to work better with Ant Design
  },
};
