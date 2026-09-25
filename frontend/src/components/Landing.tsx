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
  CheckCircle2,
} from 'lucide-react';
import heroPreview from '../assets/hero-preview.svg';

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
        'Claims are evaluated by specialist agents — coverage, exclusions, then a draft payout — with deterministic, verifiable math.',
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
        'Two clear roles — Client and Corp — each with their own workspace, backed by secure server-side authorization.',
    },
    {
      icon: Users,
      title: 'Built for Both Sides',
      description:
        'Clients track their claims; insurer staff manage documents, approvals and oversight from one shared platform.',
    },
  ];

  const steps = [
    {
      title: 'Submit',
      description: 'A policyholder files a claim with policy number, loss date and amount.',
    },
    {
      title: 'Adjudicate',
      description: 'Async workers run the agent pipeline with live, cancellable progress.',
    },
    {
      title: 'Approve',
      description: 'Insurer staff review the recommendation and set the final payout.',
    },
  ];

  return (
    <div className="relative overflow-hidden mesh-bg">
      {/* Hero */}
      <section className="page-shell px-4 pt-14 md:px-6 md:pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <span className="badge badge-neutral inline-flex gap-2 py-1 pl-2.5 pr-3">
            <Sparkles className="h-3.5 w-3.5 text-[var(--color-accent)]" />
            Agentic claims intelligence platform
          </span>

          <h1 className="mt-6 text-[2.25rem] font-extrabold leading-[1.1] tracking-[-0.03em] text-[var(--color-fg)] md:text-[3.25rem]">
            Insurance intelligence,
            <br />
            human integrity.
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-[var(--color-fg-secondary)] md:text-lg">
            insureAI reads your policy contracts, answers questions with citations, and runs
            multi-agent claim adjudication — always ending in a human approval gate.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button onClick={onRegister} className="btn btn-primary btn-lg">
              Create an account <ArrowRight className="h-4 w-4" />
            </button>
            <button onClick={onLogin} className="btn btn-secondary btn-lg">
              Sign in
            </button>
          </div>

          <p className="mt-5 text-xs text-[var(--color-fg-tertiary)]">
            Register as a <span className="font-semibold text-[var(--color-fg)]">Client</span> or{' '}
            <span className="font-semibold text-[var(--color-fg)]">Corp (Insurer Staff)</span>.
          </p>

          <button
            onClick={onExplore}
            className="mt-6 inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--color-fg-secondary)] transition-colors hover:text-[var(--color-fg)]"
          >
            Explore Q&amp;A and policies without an account
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Product preview */}
        <div className="relative mx-auto mt-12 max-w-5xl pb-4">
          <div className="soft-card card-shadow overflow-hidden p-1.5">
            <img
              src={heroPreview}
              alt="insureAI dashboard showing claim statistics, a volume chart and the approvals queue"
              className="block w-full rounded-[14px]"
              width={1200}
              height={760}
            />
          </div>
          <div
            className="pointer-events-none absolute inset-x-8 -bottom-6 -z-10 h-24 rounded-full blur-2xl"
            style={{ background: 'rgba(15, 23, 42, 0.10)' }}
            aria-hidden="true"
          />
        </div>
      </section>

      {/* Trust strip */}
      <section className="page-shell px-4 py-10 md:px-6">
        <div className="soft-card grid grid-cols-1 divide-y divide-[var(--color-border)] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {[
            { value: '25 golden questions', label: 'Normal and adversarial cases in the evaluation set' },
            { value: 'Cited answers', label: 'Retrieval grounded in your own policy corpus' },
            { value: 'Zero auto-payout', label: 'Every decision passes a human approval gate' },
          ].map((item) => (
            <div key={item.value} className="px-6 py-5">
              <div className="text-sm font-bold text-[var(--color-fg)]">{item.value}</div>
              <div className="mt-1 text-xs leading-relaxed text-[var(--color-fg-tertiary)]">
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Capabilities */}
      <section className="page-shell px-4 pb-16 md:px-6">
        <div className="mb-8 max-w-2xl">
          <span className="eyebrow">Capabilities</span>
          <h2 className="page-title mt-2">Everything an insurance workflow needs</h2>
          <p className="mt-2 text-sm leading-relaxed text-[var(--color-fg-secondary)]">
            One platform for policy understanding, claim adjudication and human oversight —
            built on retrieval you can audit.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="soft-card card-hover space-y-3 p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-[11px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] text-[var(--color-fg)]">
                  <Icon className="h-[18px] w-[18px]" strokeWidth={1.8} />
                </div>
                <h3 className="text-sm font-bold text-[var(--color-fg)]">{f.title}</h3>
                <p className="text-[13px] leading-relaxed text-[var(--color-fg-secondary)]">
                  {f.description}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* How it works */}
      <section className="page-shell px-4 pb-16 md:px-6">
        <div className="mb-8">
          <span className="eyebrow">Workflow</span>
          <h2 className="page-title mt-2">From first notice to final payout</h2>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {steps.map((step, index) => (
            <div key={step.title} className="soft-card p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-accent)] text-xs font-bold text-[var(--color-accent-contrast)]">
                  {index + 1}
                </span>
                <h3 className="text-sm font-bold text-[var(--color-fg)]">{step.title}</h3>
              </div>
              <p className="mt-3 text-[13px] leading-relaxed text-[var(--color-fg-secondary)]">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="page-shell px-4 pb-20 md:px-6">
        <div className="soft-card card-shadow flex flex-col items-start justify-between gap-6 p-8 md:flex-row md:items-center">
          <div>
            <h3 className="text-lg font-extrabold tracking-tight text-[var(--color-fg)]">
              Get started with insureAI
            </h3>
            <p className="mt-1.5 flex items-center gap-2 text-sm text-[var(--color-fg-secondary)]">
              <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" />
              Register a Client or Corp account to unlock claim submission and approvals.
            </p>
          </div>
          <button onClick={onRegister} className="btn btn-primary btn-lg shrink-0">
            Register now <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </section>
    </div>
  );
};

export default Landing;
