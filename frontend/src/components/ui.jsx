// Shared form/button primitives — pulled out of App.jsx to stop the same
// Tailwind class strings from being retyped at every call site. Visual
// output is meant to match what App.jsx had before this extraction; the
// `size` scale exists because the app used three different input/select
// paddings and four different button paddings, not because more variety
// was wanted here.

const FIELD_SIZES = {
  xs: "px-2 py-1 text-sm",
  sm: "px-2 py-2 text-sm",
  md: "px-3 py-2 text-sm",
};

export function Input({ label, size = "md", className = "", ...props }) {
  return (
    <input
      aria-label={label}
      className={`rounded-lg border border-slate-700 bg-slate-900 placeholder:text-slate-500 disabled:opacity-50 ${FIELD_SIZES[size]} ${className}`}
      {...props}
    />
  );
}

export function Select({ label, size = "md", className = "", children, ...props }) {
  return (
    <select
      aria-label={label}
      className={`rounded-lg border border-slate-700 bg-slate-900 disabled:opacity-50 ${FIELD_SIZES[size]} ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}

const BUTTON_VARIANTS = {
  primary: "bg-emerald-600 hover:bg-emerald-500",
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
