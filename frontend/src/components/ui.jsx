import { useRef } from "react";

// Shared form/button primitives — pulled out of App.jsx to stop the same
// Tailwind class strings from being retyped at every call site. The `size`
// scale exists because the app used three different input/select paddings
// and four different button paddings, not because more variety was wanted.

const FIELD_SIZES = {
  xs: "px-2 py-1 text-sm",
  sm: "px-2 py-2 text-sm",
  md: "px-3 py-2 text-sm",
};

// Field borders use slate-600 (about 3:1 on the card surface) so inputs are visible as controls.
const FIELD = "rounded-lg border border-slate-600 bg-slate-950/50 disabled:opacity-50";

export function Input({ label, size = "md", className = "", ...props }) {
  return (
    <input
      aria-label={label}
      className={`${FIELD} placeholder:text-slate-500 ${FIELD_SIZES[size]} ${className}`}
      {...props}
    />
  );
}

export function Select({ label, size = "md", className = "", children, ...props }) {
  return (
    <select aria-label={label} className={`${FIELD} ${FIELD_SIZES[size]} ${className}`} {...props}>
      {children}
    </select>
  );
}

const BUTTON_VARIANTS = {
  primary: "bg-emerald-700 text-white hover:bg-emerald-600",
  secondary: "bg-slate-700 hover:bg-slate-600",
};

const BUTTON_SIZES = {
  xs: "px-2 py-1 text-xs",
  sm: "px-3 py-1.5 text-xs",
  md: "px-3 py-2 text-sm",
  lg: "px-4 py-2 text-sm",
};

export function Button({ variant = "primary", size = "md", className = "", ...props }) {
  return (
    <button
      className={`rounded-lg font-medium disabled:opacity-50 ${BUTTON_SIZES[size]} ${BUTTON_VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

// WAI-ARIA tabs: arrow keys / Home / End move focus and selection. Panels are
// rendered by the caller (kept mounted, toggled with `hidden`) so a tab's state
// and fetched data survive switching away and back.
export function TabBar({ tabs, selected, onSelect, idBase, label }) {
  const refs = useRef([]);
  function onKeyDown(e, i) {
    let j = null;
    if (e.key === "ArrowRight") j = (i + 1) % tabs.length;
    if (e.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
    if (e.key === "Home") j = 0;
    if (e.key === "End") j = tabs.length - 1;
    if (j == null) return;
    e.preventDefault();
    onSelect(tabs[j].id);
    refs.current[j]?.focus();
  }
  return (
    <div role="tablist" aria-label={label} className="flex border-b border-slate-800">
      {tabs.map((t, i) => {
        const on = t.id === selected;
        return (
          <button
            key={t.id}
            ref={(el) => (refs.current[i] = el)}
            role="tab"
            type="button"
            id={`${idBase}-tab-${t.id}`}
            aria-selected={on}
            aria-controls={`${idBase}-panel-${t.id}`}
            tabIndex={on ? 0 : -1}
            onClick={() => onSelect(t.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`-mb-px min-h-[48px] min-w-0 flex-1 border-b-2 px-1 font-display text-[15px] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-400 sm:text-base ${
              on
                ? "border-emerald-400 font-bold text-slate-50"
                : "border-transparent font-medium text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
