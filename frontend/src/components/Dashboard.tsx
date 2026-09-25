import React, { useEffect, useState } from 'react';
import {
  FileText,
  ShieldCheck,
  Users,
  Clock,
  CheckCircle2,
  ArrowRight,
  FileSignature,
  Zap,
  Activity,
  Gauge,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import type { TabType } from './Navbar';

interface DashboardProps {
  setActiveTab: (tab: TabType) => void;
}

interface PolicyDocument {
  id: string;
  filename: string;
  status: string;
  created_at: string;
}

interface ApprovalItem {
  claim_id: string;
  policy_number: string;
  status: string;
  claim_amount_requested: string;
  recommended_payout: string;
  recommendation_reasoning: string;
}

interface ClaimRow {
  claim_id: string;
  status: string;
  claim_amount_requested: string;
  final_payout?: string | null;
}

interface UsageSummary {
  total_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
}

type Tone = 'neutral' | 'success' | 'warning' | 'danger';

const toneText: Record<Tone, string> = {
  neutral: 'text-[var(--color-fg-secondary)]',
  success: 'text-[var(--color-success)]',
  warning: 'text-[var(--color-warning)]',
  danger: 'text-[var(--color-danger)]',
};

const StatCard: React.FC<{
  label: string;
  value: React.ReactNode;
  hint: string;
  icon: React.ReactNode;
  tone?: Tone;
}> = ({ label, value, hint, icon, tone = 'neutral' }) => (
  <div className="soft-card card-hover p-5">
    <div className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)]">
      <span className={toneText[tone]}>{icon}</span>
    </div>
    <div className="mt-4 tiny-label">{label}</div>
    <div className="mt-1.5 text-[28px] font-extrabold leading-none tracking-[-0.02em] tabular-nums text-[var(--color-fg)]">
      {value}
    </div>
    <div className="mt-2 text-xs leading-relaxed text-[var(--color-fg-tertiary)]">{hint}</div>
  </div>
);

const SkeletonRow: React.FC = () => (
  <div className="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3.5 last:border-b-0">
    <div className="skeleton h-3 w-1/2" />
    <div className="skeleton ml-auto h-4 w-16 rounded-full" />
  </div>
);

const STATUS_LABELS: { key: string; label: string; tone: Tone }[] = [
  { key: 'submitted', label: 'Submitted', tone: 'neutral' },
  { key: 'processing', label: 'Processing', tone: 'neutral' },
  { key: 'pending_approval', label: 'Pending', tone: 'warning' },
  { key: 'report_ready', label: 'Report', tone: 'neutral' },
  { key: 'approved', label: 'Approved', tone: 'success' },
  { key: 'rejected', label: 'Rejected', tone: 'danger' },
];

export const Dashboard: React.FC<DashboardProps> = ({ setActiveTab }) => {
  const { user } = useAuth();
  const isCorp = user?.role === 'corp';

  const [documents, setDocuments] = useState<PolicyDocument[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [clientCount, setClientCount] = useState<number | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controllers: AbortController[] = [];
    let cancelled = false;

    const load = async () => {
      const requests: Promise<void>[] = [];
      const docCtrl = new AbortController();
      controllers.push(docCtrl);
      requests.push(
        fetch('/documents', { signal: docCtrl.signal })
          .then((res) => (res.ok ? res.json() : Promise.reject()))
          .then((data) => setDocuments(data))
          .catch((err) => {
            if (err?.name !== 'AbortError') setDocuments([]);
          })
      );

      if (isCorp) {
        const ctrl = new AbortController();
        controllers.push(ctrl);
        const opts: RequestInit = { credentials: 'include', signal: ctrl.signal };

        requests.push(
          fetch('/approvals', opts)
            .then((res) => (res.ok ? res.json() : Promise.reject()))
            .then((data) => setApprovals(Array.isArray(data) ? data : []))
            .catch((err) => {
              if (err?.name !== 'AbortError') setApprovals([]);
            })
        );

        requests.push(
          fetch('/auth/clients-count', opts)
            .then((res) => (res.ok ? res.json() : Promise.reject()))
            .then((data) => setClientCount(data.client_count))
            .catch((err) => {
              if (err?.name !== 'AbortError') setClientCount(null);
            })
        );

        requests.push(
          fetch('/claims', opts)
            .then((res) => (res.ok ? res.json() : Promise.reject()))
            .then((data) => setClaims(Array.isArray(data) ? data : []))
            .catch((err) => {
              if (err?.name !== 'AbortError') setClaims([]);
            })
        );

        requests.push(
          fetch('/usage/summary', opts)
            .then((res) => (res.ok ? res.json() : Promise.reject()))
            .then((data) => setUsage(data))
            .catch((err) => {
              if (err?.name !== 'AbortError') setUsage(null);
            })
        );
      }

      await Promise.all(requests);
      if (!cancelled) setLoading(false);
    };

    void load();
    return () => {
      cancelled = true;
      controllers.forEach((c) => c.abort());
    };
  }, [isCorp]);

  const UNDECIDED = new Set(['pending_approval', 'submitted', 'processing', 'report_ready']);
  const DECIDED = new Set(['approved', 'rejected', 'refused', 'cancelled', 'failed']);
  const pendingApprovals = approvals.filter((a) => UNDECIDED.has(a.status));
  const approvedClaims = claims.filter((c) => c.status === 'approved').length;
  const decidedClaims = claims.filter((c) => DECIDED.has(c.status)).length;

  const statusCounts = STATUS_LABELS.map((s) => ({
    ...s,
    count: claims.filter((c) => c.status === s.key).length,
  })).filter((s) => s.count > 0);
  const maxStatus = Math.max(1, ...statusCounts.map((s) => s.count));

  const throughput =
    claims.length > 0 ? Math.round((decidedClaims / claims.length) * 100) : null;

  return (
    <div className="animate-rise space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 border-b border-[var(--color-border)] pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <span className="eyebrow">
            {isCorp ? 'Insurer Operations' : 'Policyholder Portal'}
          </span>
          <h1 className="page-title mt-1.5">
            Welcome back{user ? `, ${user.email.split('@')[0]}` : ''}
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-[var(--color-fg-secondary)]">
            {isCorp
              ? 'Corpus, clients, claim volume and model spend — your operations at a glance.'
              : 'Your claims and policy documents at a glance.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => setActiveTab('qa')} className="btn btn-secondary">
            Ask insureAI
          </button>
          {isCorp ? (
            <button onClick={() => setActiveTab('approvals')} className="btn btn-primary">
              <ShieldCheck className="h-4 w-4" /> Review Approvals
            </button>
          ) : (
            <button onClick={() => setActiveTab('claims')} className="btn btn-primary">
              <FileSignature className="h-4 w-4" /> Submit Claim
            </button>
          )}
        </div>
      </div>

      {/* Stat grid */}
      {isCorp ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Documents"
            value={loading ? '—' : documents.length || 0}
            hint="Policy contracts on file"
            icon={<FileText className="h-4 w-4" strokeWidth={1.9} />}
          />
          <StatCard
            label="Clients"
            value={clientCount ?? '—'}
            hint="Registered policyholders"
            icon={<Users className="h-4 w-4" strokeWidth={1.9} />}
          />
          <StatCard
            label="Pending Approvals"
            value={pendingApprovals.length}
            hint="Awaiting your decision"
            icon={<Clock className="h-4 w-4" strokeWidth={1.9} />}
            tone="warning"
          />
          <StatCard
            label="Claims"
            value={loading ? '—' : claims.length || 0}
            hint={`${approvedClaims} approved · ${decidedClaims} decided`}
            icon={<Zap className="h-4 w-4" strokeWidth={1.9} />}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Documents"
            value={loading ? '—' : documents.length || 0}
            hint="Policy contracts on file"
            icon={<FileText className="h-4 w-4" strokeWidth={1.9} />}
          />
          <StatCard
            label="Claims"
            value="—"
            hint="Open Claim Adjudication to submit"
            icon={<FileSignature className="h-4 w-4" strokeWidth={1.9} />}
          />
          <StatCard
            label="Account"
            value="Client"
            hint="Decisions stay with insurer staff"
            icon={<Users className="h-4 w-4" strokeWidth={1.9} />}
          />
        </div>
      )}

      {/* Chart row */}
      {isCorp && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="soft-card lg:col-span-7">
            <div className="flex items-start justify-between gap-4 p-5 pb-0">
              <div>
                <span className="eyebrow">Claim Pipeline</span>
                <h3 className="mt-1 text-sm font-bold text-[var(--color-fg)]">
                  Claims by status
                </h3>
              </div>
              <span className="badge badge-neutral">{claims.length} total</span>
            </div>

            {statusCounts.length === 0 ? (
              <div className="empty-state">
                <span className="empty-icon">
                  <Activity className="h-4 w-4" />
                </span>
                <span className="font-semibold text-[var(--color-fg-secondary)]">
                  No claims yet
                </span>
                <span>Submitted claims will appear here by status.</span>
              </div>
            ) : (
              <div className="p-5 pt-4">
                <div className="flex h-44 items-end gap-3 sm:gap-5">
                  {statusCounts.map((s, i) => {
                    const barHeight = Math.max(8, Math.round((s.count / maxStatus) * 132));
                    return (
                      <div key={s.key} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                        <span className="text-[11px] font-bold tabular-nums text-[var(--color-fg-secondary)]">
                          {s.count}
                        </span>
                        <div
                          className="w-full rounded-t-[8px] bg-[var(--color-accent)]"
                          style={{
                            height: `${barHeight}px`,
                            opacity: 0.35 + (i / Math.max(1, statusCounts.length - 1)) * 0.65,
                          }}
                          title={`${s.label}: ${s.count}`}
                        />
                        <span className="truncate text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--color-fg-tertiary)]">
                          {s.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-4 border-t border-dashed border-[var(--color-border)] pt-3 text-[11px] text-[var(--color-fg-tertiary)]">
                  Live counts from the adjudication queue.
                </div>
              </div>
            )}
          </div>

          <div className="soft-card lg:col-span-5">
            <div className="p-5 pb-0">
              <span className="eyebrow">Model Usage</span>
              <h3 className="mt-1 text-sm font-bold text-[var(--color-fg)]">
                Token &amp; call accounting
              </h3>
            </div>
            <div className="space-y-4 p-5">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-xs text-[var(--color-fg-secondary)]">
                  <Activity className="h-3.5 w-3.5" /> LLM calls
                </span>
                <span className="text-sm font-bold tabular-nums text-[var(--color-fg)]">
                  {usage ? usage.total_calls.toLocaleString() : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-xs text-[var(--color-fg-secondary)]">
                  <Zap className="h-3.5 w-3.5" /> Total tokens
                </span>
                <span className="text-sm font-bold tabular-nums text-[var(--color-fg)]">
                  {usage ? usage.total_tokens.toLocaleString() : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-xs text-[var(--color-fg-secondary)]">
                  <FileText className="h-3.5 w-3.5" /> Prompt / completion
                </span>
                <span className="font-mono text-xs text-[var(--color-fg-secondary)]">
                  {usage
                    ? `${usage.total_prompt_tokens.toLocaleString()} / ${usage.total_completion_tokens.toLocaleString()}`
                    : '—'}
                </span>
              </div>

              <div className="rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] p-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 font-semibold text-[var(--color-fg)]">
                    <Gauge className="h-3.5 w-3.5" /> Claims decided
                  </span>
                  <span className="font-bold tabular-nums text-[var(--color-fg)]">
                    {throughput === null ? '—' : `${throughput}%`}
                  </span>
                </div>
                <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
                  <div
                    className="h-full rounded-full bg-[var(--color-success)] transition-all duration-500"
                    style={{ width: `${throughput ?? 0}%` }}
                  />
                </div>
                <p className="mt-2 text-[11px] text-[var(--color-fg-tertiary)]">
                  {decidedClaims} of {claims.length || 0} claims resolved.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Business content */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Recent documents */}
        <div className="soft-card overflow-hidden lg:col-span-7">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] p-5">
            <div>
              <span className="eyebrow">Policy Library</span>
              <h3 className="mt-1 text-sm font-bold text-[var(--color-fg)]">Recent Documents</h3>
            </div>
            <button
              onClick={() => setActiveTab('documents')}
              className="btn btn-ghost btn-sm"
            >
              View all <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {loading ? (
            <div>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </div>
          ) : documents.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">
                <FileText className="h-4 w-4" />
              </span>
              <span className="font-semibold text-[var(--color-fg-secondary)]">
                No documents yet
              </span>
              <span>Upload a policy contract to start asking cited questions.</span>
              <button onClick={() => setActiveTab('documents')} className="btn btn-secondary btn-sm mt-2">
                Open Policy Library
              </button>
            </div>
          ) : (
            <div className="scroll-thin overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Status</th>
                    <th className="text-right">Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.slice(0, 6).map((doc) => (
                    <tr key={doc.id}>
                      <td className="max-w-[240px] truncate font-medium text-[var(--color-fg)]">
                        {doc.filename}
                      </td>
                      <td>
                        <span className="badge badge-success">
                          <CheckCircle2 className="h-3 w-3" /> {doc.status}
                        </span>
                      </td>
                      <td className="text-right font-mono text-xs text-[var(--color-fg-tertiary)]">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pending approvals (corp only) */}
        {isCorp && (
          <div className="soft-card overflow-hidden lg:col-span-5">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] p-5">
              <div>
                <span className="eyebrow">Decision Queue</span>
                <h3 className="mt-1 text-sm font-bold text-[var(--color-fg)]">
                  Pending Approvals
                </h3>
              </div>
              <button onClick={() => setActiveTab('approvals')} className="btn btn-ghost btn-sm">
                Open queue <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {loading ? (
              <div>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </div>
            ) : pendingApprovals.length === 0 ? (
              <div className="empty-state">
                <span className="empty-icon">
                  <ShieldCheck className="h-4 w-4" />
                </span>
                <span className="font-semibold text-[var(--color-fg-secondary)]">
                  Queue is clear
                </span>
                <span>No claims are awaiting review right now.</span>
              </div>
            ) : (
              <div className="divide-y divide-[var(--color-border)]">
                {pendingApprovals.slice(0, 4).map((item) => (
                  <div key={item.claim_id} className="space-y-2 p-4 transition-colors hover:bg-[var(--color-bg-tertiary)]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-[var(--color-fg)]">
                        {item.policy_number}
                      </span>
                      <span className="badge badge-warning">
                        <Clock className="h-3 w-3" /> {item.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-[var(--color-fg-tertiary)]">Requested</span>
                      <span className="font-mono font-semibold text-[var(--color-fg-secondary)]">
                        ${item.claim_amount_requested}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-[var(--color-fg-tertiary)]">Recommended</span>
                      <span className="font-mono font-semibold text-[var(--color-success)]">
                        {item.recommended_payout ? `$${item.recommended_payout}` : '—'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* AI composer — shortcut into the Ask workspace */}
      <div className="soft-card card-shadow flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)]">
            <Sparkles className="h-4 w-4 text-[var(--color-accent)]" />
          </span>
          <div>
            <h3 className="text-sm font-bold text-[var(--color-fg)]">Ask insureAI</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-[var(--color-fg-secondary)]">
              Query the policy corpus with citations — answers refuse to fabricate outside it.
            </p>
          </div>
        </div>
        <button onClick={() => setActiveTab('qa')} className="btn btn-primary shrink-0">
          Open workspace <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default Dashboard;
