import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useNavigate } from "react-router-dom";

export default function AuthPage() {
  const nav = useNavigate();
  const { setToken } = useAuth();

  const [mode, setMode] = useState("login"); // login | register
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    setErr("");

    try {
      const payload =
        mode === "register"
          ? await api.register({ email, password, username })
          : await api.login({ email, password });

      setToken(payload.token);
      nav("/reels");
    } catch (e) {
      setErr(e?.message || "Something went wrong");
    }
  }

  return (
    <div className="min-h-screen bg-white text-black dark:bg-zinc-950 dark:text-zinc-100 flex items-center justify-center p-6">
      <div className="w-full max-w-sm border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5">
        <div className="text-lg font-semibold">OG Ecosystem</div>
        <div className="text-sm opacity-70 mt-1">
          {mode === "login" ? "Login" : "Register"}
        </div>

        <form className="mt-4 space-y-3" onSubmit={submit}>
          {mode === "register" && (
            <>
              <input
                className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-transparent"
                placeholder="Username (brand/page name)"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
              />
              <p className="text-xs text-zinc-500">
                Username = brand/page name.
              </p>
            </>
          )}

          <input
            className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-transparent"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <input
            className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-transparent"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />

          {err && <div className="text-sm text-red-500">{err}</div>}

          <button className="w-full py-2 rounded-xl bg-black text-white dark:bg-white dark:text-black">
            {mode === "login" ? "Login" : "Create account"}
          </button>
        </form>

        <button
          className="mt-3 text-sm underline opacity-80"
          onClick={() => setMode((m) => (m === "login" ? "register" : "login"))}
        >
          {mode === "login"
            ? "New user? Register"
            : "Already have account? Login"}
        </button>
      </div>
    </div>
  );
}
