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

const STAT_CARD =
  'rounded-2xl border border-[#1f1f1f] bg-[#0a0a0a] p-5 space-y-2 transition-colors hover:border-[#2e2e2e]';

const statLabel = 'flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.12em] text-[#8a8a8e]';
const statValue = 'text-3xl font-bold font-mono tracking-tight text-[#f5f5f5]';
const statHint = 'text-[11px] text-[#5c5c60]';

const StatCard: React.FC<{
  label: string;
  value: React.ReactNode;
  hint: string;
  icon: React.ReactNode;
  accent?: string;
}> = ({ label, value, hint, icon, accent }) => (
  <div className={STAT_CARD}>
    <div className={statLabel}>
      <span>{label}</span>
      <span className={accent ?? 'text-[#5c5c60]'}>{icon}</span>
    </div>
    <div className={statValue} style={accent ? { color: accent } : undefined}>
      {value}
    </div>
    <div className={statHint}>{hint}</div>
  </div>
);

export const Dashboard: React.FC<DashboardProps> = ({ setActiveTab }) => {
  const { user } = useAuth();
  const isCorp = user?.role === 'corp';

  const [documents, setDocuments] = useState<PolicyDocument[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [clientCount, setClientCount] = useState<number | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);

  useEffect(() => {
    fetch('/documents')
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setDocuments(data))
      .catch(() => setDocuments([]));
  }, []);

  useEffect(() => {
    if (!isCorp) return;

    fetch('/approvals')
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setApprovals(Array.isArray(data) ? data : []))
      .catch(() => setApprovals([]));

    fetch('/auth/clients-count')
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setClientCount(data.client_count))
      .catch(() => setClientCount(null));

    fetch('/claims', { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setClaims(Array.isArray(data) ? data : []))
      .catch(() => setClaims([]));

    fetch('/usage/summary', { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setUsage(data))
      .catch(() => setUsage(null));
  }, [isCorp]);

  const UNDECIDED = new Set(['pending_approval', 'submitted', 'processing', 'report_ready']);
  const DECIDED = new Set(['approved', 'rejected', 'refused', 'cancelled', 'failed']);
  const pendingApprovals = approvals.filter((a) => UNDECIDED.has(a.status));
  const approvedClaims = claims.filter((c) => c.status === 'approved').length;
  const decidedClaims = claims.filter((c) => DECIDED.has(c.status)).length;

  return (
    <div className="animate-rise space-y-8">
      {/* Hero Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#1f1f1f] pb-6">
        <div>
          <span className="eyebrow">
            {isCorp ? 'Insurer Operations' : 'Policyholder Portal'}
          </span>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-[#f5f5f5]">
            Welcome back{user ? `, ${user.email.split('@')[0]}` : ''}
          </h1>
          <p className="mt-1 max-w-xl text-sm text-[#9a9a9e] leading-relaxed">
            {isCorp
              ? 'Corpus, clients, claim volume and LLM spend — dark ops overview.'
              : 'Your claims and policy documents at a glance.'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={() => setActiveTab('qa')} className="btn btn-secondary btn-sm">
            Ask Question
          </button>
          {isCorp ? (
            <button onClick={() => setActiveTab('approvals')} className="btn btn-primary btn-sm">
              <ShieldCheck className="h-3.5 w-3.5" /> Review Approvals
            </button>
          ) : (
            <button onClick={() => setActiveTab('claims')} className="btn btn-primary btn-sm">
              <FileSignature className="h-3.5 w-3.5" /> Submit Claim
            </button>
          )}
        </div>
      </div>

      {/* Corp dark metric grid */}
      {isCorp ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard
            label="Documents"
            value={documents.length || 0}
            hint="Policy contracts on file"
            icon={<FileText className="h-4 w-4" />}
          />
          <StatCard
            label="Clients"
            value={clientCount ?? '—'}
            hint="Registered policyholders"
            icon={<Users className="h-4 w-4" />}
            accent="#3b82f6"
          />
          <StatCard
            label="Pending"
            value={pendingApprovals.length}
            hint="Awaiting your decision"
            icon={<Clock className="h-4 w-4" />}
            accent="#e8a33d"
          />
          <StatCard
            label="Claims"
            value={claims.length || 0}
            hint={`${approvedClaims} approved · ${decidedClaims} decided`}
            icon={<Zap className="h-4 w-4" />}
          />
          <StatCard
            label="LLM Calls"
            value={usage ? usage.total_calls : '—'}
            hint={usage ? `${usage.total_tokens.toLocaleString()} tokens` : 'Token accounting'}
            icon={<Activity className="h-4 w-4" />}
            accent="#22c55e"
          />
          <StatCard
            label="Throughput"
            value={
              claims.length > 0
                ? `${Math.round((decidedClaims / claims.length) * 100)}%`
                : '—'
            }
            hint="Claims decided"
            icon={<Gauge className="h-4 w-4" />}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Documents"
            value={documents.length || 0}
            hint="Policy contracts on file"
            icon={<FileText className="h-4 w-4" />}
          />
          <StatCard
            label="Claims"
            value="—"
            hint="Open Claim Adjudication to submit"
            icon={<FileSignature className="h-4 w-4" />}
          />
          <StatCard
            label="Account"
            value="Client"
            hint="Decisions stay with insurer staff"
            icon={<Users className="h-4 w-4" />}
            accent="#3b82f6"
          />
        </div>
      )}

      {/* Business Content */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Recent Documents */}
        <div className="soft-card lg:col-span-7 overflow-hidden">
          <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
            <div>
              <span className="eyebrow">Policy Library</span>
              <h3 className="text-sm font-semibold text-[var(--color-fg)]">Recent Documents</h3>
            </div>
            <button
              onClick={() => setActiveTab('documents')}
              className="text-xs font-medium text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)] flex items-center gap-1"
            >
              View all <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="p-6 text-center text-xs text-[var(--color-fg-tertiary)]">
              No documents yet.
            </div>
          ) : (
            <div className="scroll-thin overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--color-recessed)] text-xs font-medium text-[var(--color-fg-secondary)] border-b border-[var(--color-border)]">
                  <tr>
                    <th className="p-3.5">Document</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5 text-right">Uploaded</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {documents.slice(0, 6).map((doc) => (
                    <tr key={doc.id} className="hover:bg-[var(--color-bg-tertiary)]">
                      <td className="p-3.5 text-xs font-medium text-[var(--color-fg)]">
                        {doc.filename}
                      </td>
                      <td className="p-3.5">
                        <span className="inline-flex items-center gap-1 rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-0.5 text-[11px] font-medium text-green-400 capitalize">
                          <CheckCircle2 className="h-3 w-3" /> {doc.status}
                        </span>
                      </td>
                      <td className="p-3.5 font-mono text-xs text-right text-[var(--color-fg-tertiary)]">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pending Approvals (corp only) */}
        {isCorp && (
          <div className="soft-card lg:col-span-5 overflow-hidden">
            <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
              <div>
                <span className="eyebrow">Decision Queue</span>
                <h3 className="text-sm font-semibold text-[var(--color-fg)]">Pending Approvals</h3>
              </div>
              <button
                onClick={() => setActiveTab('approvals')}
                className="text-xs font-medium text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)] flex items-center gap-1"
              >
                Open queue <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {pendingApprovals.length === 0 ? (
              <div className="p-6 text-center text-xs text-[var(--color-fg-tertiary)]">
                No claims awaiting review.
              </div>
            ) : (
              <div className="divide-y divide-[var(--color-border)]">
                {pendingApprovals.slice(0, 4).map((item) => (
                  <div key={item.claim_id} className="p-4 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold text-[var(--color-fg)]">
                        {item.policy_number}
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                        <Clock className="h-3 w-3" /> {item.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-[var(--color-fg-tertiary)]">Requested</span>
                      <span className="font-mono text-[var(--color-fg-secondary)]">
                        ${item.claim_amount_requested}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-[var(--color-fg-tertiary)]">Recommended</span>
                      <span className="font-mono text-[var(--color-success)]">
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
    </div>
  );
};
