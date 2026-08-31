import React from 'react';
import {
  ArrowRight,
  MessageSquare,
  ShieldCheck,
  Scale,
  FileSearch,
  Users,
  Lock,
  Sparkles,
} from 'lucide-react';

interface LandingProps {
  onLogin: () => void;
  onRegister: () => void;
  onExplore: () => void;
}

export const Landing: React.FC<LandingProps> = ({ onLogin, onRegister, onExplore }) => {
  const features = [
    {
      icon: MessageSquare,
      title: 'Grounded Policy Q&A',
      description:
        'Ask questions directly against your insurance contracts and get cited, date-aware answers grounded in the actual policy text.',
    },
    {
      icon: Scale,
      title: 'Multi-Agent Adjudication',
      description:
        'Claims are evaluated by a sequence of specialist agents — coverage, exclusions, then a draft payout — with deterministic, verifiable math.',
    },
    {
      icon: ShieldCheck,
      title: 'Human-in-the-Loop Approval',
      description:
        'No automated payout. Every recommendation lands in an approval queue for insurer staff to review, override, or reject.',
    },
    {
      icon: FileSearch,
      title: 'End-to-End Audit Trace',
      description:
        'Every step of a workflow is logged and reviewable, giving full transparency into how each decision was reached.',
    },
    {
      icon: Lock,
      title: 'Role-Based Access Control',
      description:
        'Two clear roles — Client and Corp — each with their own page, backed by secure server-side authorization.',
    },
    {
      icon: Users,
      title: 'Built for Both Sides',
      description:
        'Clients track their claims; insurer staff manage documents, approvals and oversight from one shared platform.',
    },
  ];

  return (
    <div className="relative overflow-hidden">
      {/* Ambient background glow */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(60% 50% at 50% 0%, rgba(255,255,255,0.06) 0%, transparent 70%)',
        }}
      />

      {/* Hero */}
      <section className="mx-auto max-w-5xl px-6 pt-20 pb-24 text-center md:pt-28">
        <div className="mx-auto flex max-w-2xl flex-col items-center text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-panel-elevated)] px-3 py-1 text-[11px] font-medium text-[var(--color-fg-secondary)]">
            <Sparkles className="h-3.5 w-3.5 text-[var(--color-accent)]" />
            AI-assisted claims adjudication platform
          </div>

          <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight text-[var(--color-fg)] md:text-6xl md:leading-[1.1]">
            Insurance intelligence,
            <br />
            <span className="text-[var(--color-accent)]">human integrity.</span>
          </h1>

          <p className="mt-6 max-w-xl text-base text-[var(--color-fg-secondary)] md:text-lg leading-relaxed">
            Domain Copilot reads your policy contracts, answers questions with citations, and
            runs multi-agent claim adjudication — always ending in a human approval gate.
          </p>

          <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row">
            <button onClick={onRegister} className="btn btn-primary px-6 py-3 text-sm">
              Create an account <ArrowRight className="h-4 w-4" />
            </button>
            <button onClick={onLogin} className="btn btn-secondary px-6 py-3 text-sm">
              Sign in
            </button>
          </div>

          <p className="mt-6 text-xs text-[var(--color-fg-tertiary)]">
            New here? Register as a <span className="text-[var(--color-fg)]">Client</span> or{' '}
            <span className="text-[var(--color-fg)]">Corp (Insurer Staff)</span>.
          </p>

          <button
            onClick={onExplore}
            className="mt-10 flex items-center gap-1.5 text-xs font-medium text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)]"
          >
            Or explore Q&A and policies without an account <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="mb-10 text-center">
          <span className="eyebrow">Capabilities</span>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-[var(--color-fg)] md:text-3xl">
            Everything an insurance workflow needs
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="soft-card p-6 space-y-3 transition-transform duration-200 hover:-translate-y-0.5"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] text-[var(--color-accent)]">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--color-fg)]">{f.title}</h3>
                <p className="text-[13px] leading-relaxed text-[var(--color-fg-secondary)]">
                  {f.description}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA band */}
      <section className="mx-auto max-w-4xl px-6 pb-24">
        <div className="soft-card flex flex-col items-center justify-between gap-6 p-8 md:flex-row">
          <div>
            <h3 className="text-lg font-bold text-[var(--color-fg)]">
              Get started with Domain Copilot
            </h3>
            <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
              Register a Client or Corp account to unlock claim submission and approvals.
            </p>
          </div>
          <button onClick={onRegister} className="btn btn-primary px-5 py-2.5 text-sm">
            Register now
          </button>
        </div>
      </section>
    </div>
  );
};
