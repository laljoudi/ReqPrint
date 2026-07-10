import { useState } from "react";
import { login } from "../lib/api";

// Username/password gate shown before the app is usable. Calls POST /api/login.
export default function LoginScreen({ onLoggedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      onLoggedIn();
    } catch (err) {
      setError(err.message || "Incorrect username or password. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm flex flex-col items-center text-center gap-3"
      >
        <div className="flex items-center justify-center w-[44px] h-[44px] rounded-lg bg-accent text-white font-bold text-2xl shrink-0">
          R
        </div>
        <h1 className="text-2xl font-semibold text-ink mt-2">Sign in to your workspace</h1>
        <p className="text-sm text-muted">
          Turn plain-language descriptions into structured software requirements.
        </p>

        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          autoComplete="username"
          className="w-full mt-4 rounded-lg border border-border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
        />

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoComplete="current-password"
          className="w-full rounded-lg border border-border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
        />

        {error && (
          <div className="w-full rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3.5 py-2.5 text-left">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-accent hover:bg-accent-dark text-white font-medium py-2.5 text-sm transition-colors disabled:opacity-60"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>

        <p className="text-xs text-muted mt-1">
          Demo access - enter the username/password from your .env file.
        </p>
      </form>
    </div>
  );
}
