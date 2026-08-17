import { Outlet, NavLink, useLocation } from "react-router-dom";

export default function Layout() {
  const loc = useLocation();

  return (
    <div className="min-h-screen bg-white text-black dark:bg-zinc-950 dark:text-zinc-100">
      <div className="max-w-md mx-auto min-h-screen pb-16">
        {/* Top bar */}
        <div className="sticky top-0 z-10 bg-white/80 dark:bg-zinc-950/80 backdrop-blur border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold">Replica Insta</div>
            <div className="text-xs opacity-70">{loc.pathname}</div>
          </div>
        </div>

        <Outlet />

        {/* Bottom nav */}
        <div className="fixed bottom-0 left-0 right-0 border-t border-zinc-200 dark:border-zinc-800 bg-white/90 dark:bg-zinc-950/90 backdrop-blur">
          <div className="max-w-md mx-auto flex">
            <Tab to="/reels" label="Reels" />
            <Tab to="/profile" label="Profile" />
          </div>
        </div>
      </div>
    </div>
  );
}

function Tab({ to, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex-1 text-center py-3 text-sm ${
          isActive ? "font-semibold" : "opacity-70"
        }`
      }
    >
      {label}
    </NavLink>
  );
}
