import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./auth.js"; // patches window.fetch to attach an anonymous Supabase session
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
