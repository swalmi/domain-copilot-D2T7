import React, { useState } from 'react';
import { ArrowLeft, UserPlus, Building2, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../context/AuthContext';

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
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-lg">
        <button
          onClick={onBack}
          className="mb-6 flex items-center gap-1.5 text-xs font-medium text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to home
        </button>

        <div className="soft-card p-8 space-y-6 animate-rise">
          <div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--color-border-light)] bg-[var(--color-bg-secondary)] text-[var(--color-fg)]">
              <UserPlus className="h-5 w-5" />
            </div>
            <h1 className="mt-4 text-2xl font-bold tracking-tight text-[var(--color-fg)]">
              Create your account
            </h1>
            <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
              Register and choose your role. Each role unlocks its own set of pages.
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
                placeholder="Minimum 8 characters"
                minLength={8}
                required
                autoComplete="new-password"
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-medium text-[var(--color-fg-secondary)]">
                Choose your role
              </label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {roles.map((r) => {
                  const Icon = r.icon;
                  const selected = role === r.value;
                  return (
                    <button
                      type="button"
                      key={r.value}
                      onClick={() => setRole(r.value)}
                      className={`flex flex-col items-start gap-1.5 rounded-xl border p-3.5 text-left transition-all ${
                        selected
                          ? 'border-[var(--color-accent)] bg-[var(--color-active-bg)] text-[var(--color-active-fg)]'
                          : 'border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] text-[var(--color-fg)] hover:border-[var(--color-border)]'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4" />
                        <span className="text-sm font-semibold">{r.label}</span>
                      </div>
                      <span className={`text-[11px] leading-relaxed ${selected ? 'opacity-90' : 'text-[var(--color-fg-secondary)]'}`}>
                        {r.description}
                      </span>
                    </button>
                  );
                })}
              </div>
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
              {busy ? 'Creating account…' : 'Register'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
