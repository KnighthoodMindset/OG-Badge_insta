import { useNavigate } from "react-router-dom";
import { useTheme } from "../theme";

export default function SettingsPage() {
  const nav = useNavigate();
  const { mode, toggle } = useTheme();

  return (
    <div className="p-4">
      <div className="flex items-center gap-3">
        <button
          className="px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-800 text-sm"
          onClick={() => nav(-1)}
        >
          Back
        </button>
        <div className="font-semibold">Settings</div>
      </div>

      <div className="mt-4 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-4">
        <div className="font-semibold">Theme</div>
        <div className="text-sm opacity-70 mt-1">Current: {mode}</div>
        <button
          className="mt-3 px-4 py-2 rounded-xl bg-black text-white dark:bg-white dark:text-black"
          onClick={toggle}
        >
          Toggle Light/Dark
        </button>
      </div>

      <div className="mt-4 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-4">
        <div className="font-semibold">Are you an OG vendor?</div>
        <div className="text-sm opacity-70 mt-1">
          Apply for badge to verify your original page.
        </div>

        <button
          className="mt-3 w-full py-2 rounded-xl border border-zinc-200 dark:border-zinc-800"
          onClick={() => nav("/apply")}
        >
          Apply for badge
        </button>
      </div>
    </div>
  );
}
