import React, { useState } from 'react';
import { ArrowLeft, LogIn, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Brand } from './Brand';
import authSpot from '../assets/auth-spot.svg';

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
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12 mesh-bg">
      <div className="w-full max-w-4xl">
        <button
          onClick={onBack}
          className="mb-6 inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--color-fg-secondary)] transition-colors hover:text-[var(--color-fg)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to home
        </button>

        <div className="soft-card card-shadow animate-rise grid grid-cols-1 overflow-hidden lg:grid-cols-2">
          {/* Visual panel */}
          <div className="hidden flex-col justify-between border-r border-[var(--color-border)] bg-[var(--color-bg-tertiary)] p-8 lg:flex">
            <Brand />
            <div className="py-6">
              <img
                src={authSpot}
                alt="Policy document verified with an AI-assisted shield badge"
                className="mx-auto w-full max-w-[340px]"
                width={520}
                height={420}
              />
            </div>
            <div>
              <span className="eyebrow">Secure access</span>
              <h2 className="mt-2 text-xl font-extrabold tracking-tight text-[var(--color-fg)]">
                One account, your whole workspace
              </h2>
              <ul className="mt-4 space-y-2.5">
                {[
                  'Cited answers grounded in your policy corpus',
                  'Live claim pipeline with cancellable jobs',
                  'Full audit trace on every decision',
                ].map((line) => (
                  <li
                    key={line}
                    className="flex items-start gap-2 text-[13px] leading-relaxed text-[var(--color-fg-secondary)]"
                  >
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-success)]" />
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Form */}
          <div className="p-6 sm:p-8">
            <div className="flex h-11 w-11 items-center justify-center rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] text-[var(--color-fg)]">
              <LogIn className="h-5 w-5" strokeWidth={1.9} />
            </div>
            <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-[var(--color-fg)]">
              Welcome back
            </h1>
            <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-fg-secondary)]">
              Sign in to your insureAI account. Your role is determined by the account in the
              database.
            </p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label
                  htmlFor="login-email"
                  className="mb-1.5 block text-xs font-semibold text-[var(--color-fg-secondary)]"
                >
                  Email
                </label>
                <input
                  id="login-email"
                  type="email"
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  autoComplete="email"
                />
              </div>

              <div>
                <label
                  htmlFor="login-password"
                  className="mb-1.5 block text-xs font-semibold text-[var(--color-fg-secondary)]"
                >
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  autoComplete="current-password"
                />
              </div>

              {error && <div className="alert alert-danger">{error}</div>}

              <button
                type="submit"
                className="btn btn-primary w-full justify-center py-2.5"
                disabled={busy}
              >
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
            </form>

            <div className="mt-5 flex items-start gap-2 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3.5 py-3 text-[11px] leading-relaxed text-[var(--color-fg-secondary)]">
              <ShieldCheck className="mt-px h-4 w-4 shrink-0 text-[var(--color-success)]" />
              Secure session via httpOnly cookie. No role selection here — use your registered
              account.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
