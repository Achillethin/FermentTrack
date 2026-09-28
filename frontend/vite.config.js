import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// base: "/FermentTrack/" matches this repo's GitHub Pages project-site URL
// (https://<user>.github.io/FermentTrack/). Override via VITE_BASE if the
// repo is renamed or served from a custom domain (set VITE_BASE=/).
export default defineConfig({
  base: process.env.VITE_BASE || "/FermentTrack/",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "FermentTrack",
        short_name: "FermentTrack",
        description: "Batch journal and smart reminders for serious fermenters",
        start_url: process.env.VITE_BASE || "/FermentTrack/",
        display: "standalone",
        background_color: "#120f0c",
        theme_color: "#120f0c",
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
        ],
      },
      workbox: {
        // Keep the Google Fonts CSS/files after first load so the installed app renders offline.
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\//,
            handler: "StaleWhileRevalidate",
            options: { cacheName: "fonts" },
          },
        ],
      },
    }),
  ],
});
