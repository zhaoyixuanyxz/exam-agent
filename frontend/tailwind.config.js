/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        mist: "#f4f7fb",
        paper: "#faf8f5",
        softblue: "#dbeafe",
        softmint: "#d1fae5",
        softlilac: "#ede9fe",
      },
    },
  },
  plugins: [],
};
