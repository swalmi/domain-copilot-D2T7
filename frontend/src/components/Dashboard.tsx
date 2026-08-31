import React, { useEffect, useState } from 'react';
import {
  FileText,
  ShieldCheck,
  Users,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  FileSignature,
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

export const Dashboard: React.FC<DashboardProps> = ({ setActiveTab }) => {
  const { user } = useAuth();
  const isCorp = user?.role === 'corp';

  const [documents, setDocuments] = useState<PolicyDocument[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [clientCount, setClientCount] = useState<number | null>(null);

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
  }, [isCorp]);

  const pendingApprovals = approvals.filter((a) => a.status === 'pending_approval');

  return (
    <div className="animate-rise space-y-8">
      {/* Hero Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--color-border)] pb-6">
        <div>
          <span className="eyebrow">
            {isCorp ? 'Insurer Operations' : 'Policyholder Portal'}
          </span>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-[var(--color-fg)]">
            Welcome back{user ? `, ${user.email.split('@')[0]}` : ''}
          </h1>
          <p className="mt-1 max-w-xl text-sm text-[var(--color-fg-secondary)] leading-relaxed">
            Your {isCorp ? 'approvals, policy documents and client overview' : 'claims and policy documents'} at a glance.
          </p>
        </div>

        {/* Quick Actions */}
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

      {/* Business Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="soft-card p-5 space-y-2">
          <div className="flex items-center justify-between text-xs font-medium text-[var(--color-fg-secondary)]">
            <span>Policy Documents</span>
            <FileText className="h-4 w-4 text-[var(--color-fg-tertiary)]" />
          </div>
          <div className="text-3xl font-bold font-mono tracking-tight text-[var(--color-fg)]">
            {documents.length || '—'}
          </div>
          <div className="text-[11px] text-[var(--color-fg-tertiary)]">
            Live policy contracts on file
          </div>
        </div>

        <div className="soft-card p-5 space-y-2">
          <div className="flex items-center justify-between text-xs font-medium text-[var(--color-fg-secondary)]">
            <span>Pending Approvals</span>
            <Clock className="h-4 w-4 text-[var(--color-warning)]" />
          </div>
          <div className="text-3xl font-bold font-mono tracking-tight text-[var(--color-warning)]">
            {isCorp ? pendingApprovals.length : '—'}
          </div>
          <div className="text-[11px] text-[var(--color-fg-tertiary)]">
            {isCorp ? 'Awaiting your review' : 'Available to insurer staff'}
          </div>
        </div>

        <div className="soft-card p-5 space-y-2">
          <div className="flex items-center justify-between text-xs font-medium text-[var(--color-fg-secondary)]">
            <span>Clients</span>
            <Users className="h-4 w-4 text-[var(--color-fg-tertiary)]" />
          </div>
          <div className="text-3xl font-bold font-mono tracking-tight text-[var(--color-fg)]">
            {isCorp ? (clientCount ?? '—') : '—'}
          </div>
          <div className="text-[11px] text-[var(--color-fg-tertiary)]">
            {isCorp ? 'Registered policyholders' : 'Insurer-only metric'}
          </div>
        </div>
      </div>

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
                        <AlertTriangle className="h-3 w-3" /> PENDING
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
                        ${item.recommended_payout}
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
