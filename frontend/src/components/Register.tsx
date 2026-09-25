import React, { useState } from 'react';
import { ArrowLeft, UserPlus, Building2, User, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../context/AuthContext';
import { Brand } from './Brand';
import authSpot from '../assets/auth-spot.svg';

interface RegisterProps {
  onBack: () => void;
}

export const Register: React.FC<RegisterProps> = ({ onBack }) => {
  const { signup } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('client');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signup(email, password, role);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setBusy(false);
    }
  };

  const roles: { value: UserRole; label: string; description: string; icon: typeof User }[] = [
    {
      value: 'client',
      label: 'Client',
      description: 'Policyholder — submit and track your own claims.',
      icon: User,
    },
    {
      value: 'corp',
      label: 'Corp (Insurer Staff)',
      description: 'Insurance company staff — review, approve and manage claims.',
      icon: Building2,
    },
  ];

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
              <span className="eyebrow">Two roles</span>
              <h2 className="mt-2 text-xl font-extrabold tracking-tight text-[var(--color-fg)]">
                Pick the workspace you need
              </h2>
              <p className="mt-2 text-[13px] leading-relaxed text-[var(--color-fg-secondary)]">
                Clients file and follow claims. Insurer staff ingest policies, review
                recommendations and approve payouts.
              </p>
            </div>
          </div>

          {/* Form */}
          <div className="p-6 sm:p-8">
            <div className="flex h-11 w-11 items-center justify-center rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] text-[var(--color-fg)]">
              <UserPlus className="h-5 w-5" strokeWidth={1.9} />
            </div>
            <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-[var(--color-fg)]">
              Create your account
            </h1>
            <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-fg-secondary)]">
              Register and choose your role. Each role unlocks its own set of pages.
            </p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label
                  htmlFor="register-email"
                  className="mb-1.5 block text-xs font-semibold text-[var(--color-fg-secondary)]"
                >
                  Email
                </label>
                <input
                  id="register-email"
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
                  htmlFor="register-password"
                  className="mb-1.5 block text-xs font-semibold text-[var(--color-fg-secondary)]"
                >
                  Password
                </label>
                <input
                  id="register-password"
                  type="password"
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  minLength={8}
                  required
                  autoComplete="new-password"
                />
              </div>

              <div>
                <span className="mb-2 block text-xs font-semibold text-[var(--color-fg-secondary)]">
                  Choose your role
                </span>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {roles.map((r) => {
                    const Icon = r.icon;
                    const selected = role === r.value;
                    return (
                      <button
                        type="button"
                        key={r.value}
                        onClick={() => setRole(r.value)}
                        aria-pressed={selected}
                        className={`flex flex-col items-start gap-1.5 rounded-[12px] border p-3.5 text-left transition-all ${
                          selected
                            ? 'border-[var(--color-accent)] bg-[var(--color-active-bg)] text-[var(--color-active-fg)] shadow-[0_4px_14px_rgba(15,23,42,0.14)]'
                            : 'border-[var(--color-border)] bg-[var(--color-bg-secondary)] text-[var(--color-fg)] hover:border-[var(--color-fg-tertiary)]'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4" strokeWidth={1.9} />
                          <span className="text-sm font-bold">{r.label}</span>
                        </div>
                        <span
                          className={`text-[11px] leading-relaxed ${
                            selected ? 'opacity-90' : 'text-[var(--color-fg-secondary)]'
                          }`}
                        >
                          {r.description}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {error && <div className="alert alert-danger">{error}</div>}

              <button
                type="submit"
                className="btn btn-primary w-full justify-center py-2.5"
                disabled={busy}
              >
                {busy ? 'Creating account…' : 'Register'}
              </button>
            </form>

            <div className="mt-5 flex items-start gap-2 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3.5 py-3 text-[11px] leading-relaxed text-[var(--color-fg-secondary)]">
              <ShieldCheck className="mt-px h-4 w-4 shrink-0 text-[var(--color-success)]" />
              Roles are enforced server-side — the UI only reflects what the API allows.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;
