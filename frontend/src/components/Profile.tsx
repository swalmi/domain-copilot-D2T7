import React, { useEffect, useState } from 'react';
import {
  FileText,
  FileSignature,
  CheckCircle2,
  Clock,
  Mail,
  User as UserIcon,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface ClaimRow {
  claim_id: string;
  policy_number: string;
  status: string;
  claim_amount_requested: string;
  created_at?: string;
}

interface PolicyDocument {
  id: string;
  filename: string;
}

const statusPill = (status: string) => {
  const base = 'badge';
  if (status === 'approved') return `${base} badge-success`;
  if (['rejected', 'cancelled', 'refused', 'failed'].includes(status))
    return `${base} badge-danger`;
  if (status === 'pending_approval') return `${base} badge-warning`;
  return `${base} badge-neutral`;
};

type Tone = 'neutral' | 'success' | 'warning';

const toneClass: Record<Tone, string> = {
  neutral: 'text-[var(--color-fg-secondary)]',
  success: 'text-[var(--color-success)]',
  warning: 'text-[var(--color-warning)]',
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
      <span className={toneClass[tone]}>{icon}</span>
    </div>
    <div className="mt-4 tiny-label">{label}</div>
    <div className="mt-1.5 text-[28px] font-extrabold leading-none tracking-[-0.02em] tabular-nums text-[var(--color-fg)]">
      {value}
    </div>
    <div className="mt-2 text-xs leading-relaxed text-[var(--color-fg-tertiary)]">{hint}</div>
  </div>
);

const initials = (email: string): string =>
  email
    .split('@')[0]
    .split(/[._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('') || '?';

export const Profile: React.FC = () => {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<PolicyDocument[]>([]);
  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/documents', { credentials: 'include' })
        .then((res) => (res.ok ? res.json() : Promise.reject()))
        .catch(() => []),
      fetch('/claims', { credentials: 'include' })
        .then((res) => (res.ok ? res.json() : Promise.reject()))
        .catch(() => []),
    ]).then(([docs, rows]) => {
      setDocuments(Array.isArray(docs) ? docs : []);
      setClaims(Array.isArray(rows) ? rows : []);
      setLoading(false);
    });
  }, []);

  const UNDECIDED = new Set(['pending_approval', 'submitted', 'processing', 'report_ready']);
  const awaiting = claims.filter((c) => UNDECIDED.has(c.status)).length;
  const approved = claims.filter((c) => c.status === 'approved').length;
  const recent = [...claims]
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
    .slice(0, 5);

  return (
    <div className="animate-rise space-y-6">
      {/* Page header */}
      <div className="border-b border-[var(--color-border)] pb-6">
        <span className="eyebrow">Policyholder Portal</span>
        <h1 className="page-title mt-1.5">Your Profile</h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-[var(--color-fg-secondary)]">
          Account details, document access and your claim activity at a glance.
        </p>
      </div>

      {/* Account card */}
      <div className="soft-card p-6">
        <div className="flex items-center gap-4">
          <span className="avatar h-14 w-14 text-lg">
            {user?.email ? initials(user.email) : <UserIcon className="h-6 w-6" />}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="truncate text-base font-bold text-[var(--color-fg)]">
                {user?.email ?? '—'}
              </span>
              <span className="badge badge-neutral">{user?.role ?? 'client'}</span>
            </div>
            <div className="mt-1.5 flex items-center gap-1.5 text-xs text-[var(--color-fg-tertiary)]">
              <Mail className="h-3.5 w-3.5" />
              Read-only access — claim decisions stay with insurer staff.
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Documents"
          value={loading ? '—' : documents.length || 0}
          hint="Policy contracts available to you"
          icon={<FileText className="h-4 w-4" strokeWidth={1.9} />}
        />
        <StatCard
          label="My Claims"
          value={loading ? '—' : claims.length || 0}
          hint="Claims you have submitted"
          icon={<FileSignature className="h-4 w-4" strokeWidth={1.9} />}
        />
        <StatCard
          label="Approved"
          value={approved}
          hint="Claims approved by the insurer"
          icon={<CheckCircle2 className="h-4 w-4" strokeWidth={1.9} />}
          tone="success"
        />
        <StatCard
          label="Awaiting"
          value={awaiting}
          hint="In review or awaiting decision"
          icon={<Clock className="h-4 w-4" strokeWidth={1.9} />}
          tone="warning"
        />
      </div>

      {/* Recent claims */}
      <div className="soft-card overflow-hidden">
        <div className="border-b border-[var(--color-border)] p-5">
          <span className="eyebrow">Activity</span>
          <h3 className="mt-1 text-sm font-bold text-[var(--color-fg)]">Recent Claims</h3>
        </div>
        {loading ? (
          <div>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="flex items-center gap-4 border-b border-[var(--color-border)] px-5 py-4 last:border-b-0"
              >
                <div className="skeleton h-3 w-32" />
                <div className="skeleton ml-auto h-4 w-20 rounded-full" />
              </div>
            ))}
          </div>
        ) : recent.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">
              <FileSignature className="h-4 w-4" />
            </span>
            <span className="font-semibold text-[var(--color-fg-secondary)]">No claims yet</span>
            <span>Submit one from Claim Adjudication to see it here.</span>
          </div>
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>Status</th>
                  <th className="text-right">Requested</th>
                  <th className="text-right">Filed</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((c) => (
                  <tr key={c.claim_id}>
                    <td className="font-mono text-xs font-semibold text-[var(--color-fg)]">
                      {c.policy_number}
                    </td>
                    <td>
                      <span className={statusPill(c.status)}>
                        {c.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </td>
                    <td className="text-right font-mono text-xs text-[var(--color-fg-secondary)]">
                      ${c.claim_amount_requested}
                    </td>
                    <td className="text-right font-mono text-xs text-[var(--color-fg-tertiary)]">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Profile;
