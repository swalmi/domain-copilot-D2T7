import React, { useState } from 'react';
import { ArrowLeft, LogIn, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface LoginProps {
  onBack: () => void;
}

export const Login: React.FC<LoginProps> = ({ onBack }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <button
          onClick={onBack}
          className="mb-6 flex items-center gap-1.5 text-xs font-medium text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to home
        </button>

        <div className="soft-card p-8 space-y-6 animate-rise">
          <div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--color-border-light)] bg-[var(--color-bg-secondary)] text-[var(--color-fg)]">
              <LogIn className="h-5 w-5" />
            </div>
            <h1 className="mt-4 text-2xl font-bold tracking-tight text-[var(--color-fg)]">
              Welcome back
            </h1>
            <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
              Sign in to your Domain Copilot account. Your role is determined by the account in the database.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
                Email
              </label>
              <input
                type="email"
                className="karen-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
                Password
              </label>
              <input
                type="password"
                className="karen-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
              />
            </div>

            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary w-full justify-center text-sm py-2.5"
              disabled={busy}
            >
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="flex items-center gap-2 rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] px-3 py-2.5 text-[11px] text-[var(--color-fg-secondary)]">
            <ShieldCheck className="h-4 w-4 text-[var(--color-success)]" />
            Secure session via httpOnly cookie. No role selection here — use your registered account.
          </div>
        </div>
      </div>
    </div>
  );
};
