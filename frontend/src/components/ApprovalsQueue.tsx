import React, { useCallback, useEffect, useState } from 'react';
import {
  ShieldCheck,
  CheckCircle,
  XCircle,
  Edit3,
  AlertTriangle,
  FileText,
  Trash2,
  Eye,
  User,
  Calendar,
  DollarSign,
  Quote,
} from 'lucide-react';

interface Citation {
  policy_id?: string;
  page?: number;
  section?: string;
  text_preview?: string;
  text?: string;
  chunk_id?: string;
}

interface ApprovalItem {
  claim_id: string;
  user_id?: string | null;
  policy_number: string;
  date_of_loss: string;
  incident_description: string;
  status: string;
  claim_amount_requested: string;
  recommended_payout?: string | null;
  adjusted_payout?: string | null;
  final_payout?: string | null;
  deductible_applied?: string | null;
  policy_limit?: string | null;
  recommendation_reasoning?: string | null;
  ai_justification?: string | null;
  admin_justification?: string | null;
  final_justification?: string | null;
  adjuster_notes?: string | null;
  citations?: Citation[];
  error_message?: string | null;
  created_at: string;
  updated_at?: string | null;
}

const DECIDED = new Set(['approved', 'rejected', 'refused', 'cancelled', 'failed']);
const UNDECIDED = new Set(['pending_approval', 'submitted', 'processing', 'report_ready']);

const statusPill = (status: string) => {
  const base = 'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium';
  if (status === 'approved')
    return `${base} border border-green-500/30 bg-green-500/10 text-green-400`;
  if (['rejected', 'cancelled', 'refused', 'failed'].includes(status))
    return `${base} border border-red-500/30 bg-red-500/10 text-red-400`;
  if (status === 'pending_approval')
    return `${base} border border-amber-500/30 bg-amber-500/10 text-amber-400`;
  return `${base} border border-[var(--color-border-light)] bg-[var(--color-bg-tertiary)] text-[var(--color-fg-secondary)]`;
};

export const ApprovalsQueue: React.FC = () => {
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [selected, setSelected] = useState<ApprovalItem | null>(null);

  // Editable review fields
  const [editPayout, setEditPayout] = useState<string>('');
  const [editJustification, setEditJustification] = useState<string>('');
  const [editNotes, setEditNotes] = useState<string>('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string>('');
  const [busy, setBusy] = useState(false);

  const fetchClaims = useCallback(async () => {
    try {
      const res = await fetch('/claims', { credentials: 'include' });
      if (res.ok) {
        const data: ApprovalItem[] = await res.json();
        setItems(data);
        return;
      }
    } catch {
      // fall through
    }
    // Fallback to /approvals if /claims unavailable
    try {
      const res = await fetch('/approvals', { credentials: 'include' });
      if (res.ok) setItems(await res.json());
    } catch {
      // offline
    }
  }, []);

  useEffect(() => {
    fetchClaims();
  }, [fetchClaims]);

  const openDetail = (item: ApprovalItem) => {
    setSelected(item);
    setEditPayout(item.adjusted_payout || item.recommended_payout || '');
    setEditJustification(item.admin_justification || item.ai_justification || '');
    setEditNotes(item.adjuster_notes || '');
    setActionError('');
  };

  const closeDetail = () => {
    setSelected(null);
    setActionError('');
  };

  const sendDecision = async (decision: 'approve' | 'reject') => {
    if (!selected) return;
    setBusy(true);
    setActionError('');
    try {
      const body: Record<string, string> = {};
      if (editPayout && editPayout !== (selected.recommended_payout || '')) {
        body.adjusted_payout = editPayout;
      } else if (decision === 'approve' && editPayout) {
        body.adjusted_payout = editPayout;
      }
      if (editJustification && editJustification !== (selected.ai_justification || '')) {
        body.justification = editJustification;
      }
      if (editNotes.trim()) body.notes = editNotes.trim();

      const res = await fetch(`/approvals/${selected.claim_id}/${decision}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Decision failed (${res.status})`);
      }

      const newStatus = decision === 'approve' ? 'approved' : 'rejected';
      setItems((prev) =>
        prev.map((item) =>
          item.claim_id === selected.claim_id
            ? {
                ...item,
                status: newStatus,
                adjusted_payout: body.adjusted_payout || item.adjusted_payout,
                admin_justification: body.justification || item.admin_justification,
                final_justification: body.justification || item.final_justification,
                adjuster_notes: body.notes || item.adjuster_notes,
                final_payout: body.adjusted_payout || item.final_payout,
              }
            : item
        )
      );
      setSelected((prev) =>
        prev
          ? {
              ...prev,
              status: newStatus,
              adjusted_payout: body.adjusted_payout || prev.adjusted_payout,
              admin_justification: body.justification || prev.admin_justification,
              final_justification: body.justification || prev.final_justification,
              adjuster_notes: body.notes || prev.adjuster_notes,
              final_payout: body.adjusted_payout || prev.final_payout,
            }
          : prev
      );
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Decision failed');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (claimId: string) => {
    setActionError('');
    try {
      const res = await fetch(`/claims/${claimId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Delete failed (${res.status})`);
      }
      setItems((prev) => prev.filter((c) => c.claim_id !== claimId));
      if (selected?.claim_id === claimId) closeDetail();
      setConfirmDeleteId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Delete failed');
      setConfirmDeleteId(null);
    }
  };

  const filteredItems = items.filter((item) => {
    if (filter === 'pending') return UNDECIDED.has(item.status) || item.status === 'pending_approval';
    if (filter === 'approved') return item.status === 'approved';
    if (filter === 'rejected') return item.status === 'rejected';
    return true;
  });

  const pendingCount = items.filter(
    (i) => i.status === 'pending_approval' || UNDECIDED.has(i.status)
  ).length;

  return (
    <div className="animate-rise space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="eyebrow">Human-in-the-Loop Gate</span>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-[var(--color-fg)]">
            Adjuster Approval Queue
          </h2>
          <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
            Review full claim detail, edit AI payout or justification, then approve or deny.{' '}
            {pendingCount} awaiting decision.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {['all', 'pending', 'approved', 'rejected'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`chip capitalize ${filter === f ? 'chip-active' : ''}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {actionError}
        </div>
      )}

      {/* Claims table */}
      <div className="soft-card overflow-hidden">
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--color-border)] bg-[var(--color-recessed)] text-xs font-medium text-[var(--color-fg-secondary)]">
              <tr>
                <th className="p-3.5">Policy</th>
                <th className="p-3.5">User</th>
                <th className="p-3.5">Requested</th>
                <th className="p-3.5">AI Payout</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">AI Decision</th>
                <th className="p-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {filteredItems.map((item) => {
                const undecided = UNDECIDED.has(item.status);
                const decided = DECIDED.has(item.status);
                const canDelete = decided && !['pending_approval', 'submitted', 'processing', 'report_ready'].includes(item.status);
                return (
                  <tr key={item.claim_id} className="hover:bg-[var(--color-bg-tertiary)]">
                    <td className="p-3.5 font-mono text-xs font-semibold text-[var(--color-fg)]">
                      {item.policy_number}
                    </td>
                    <td className="p-3.5 font-mono text-[11px] text-[var(--color-fg-secondary)]">
                      {item.user_id ? item.user_id.slice(0, 8) + '…' : '—'}
                    </td>
                    <td className="p-3.5 font-mono text-xs text-[var(--color-fg-secondary)]">
                      ${item.claim_amount_requested}
                    </td>
                    <td className="p-3.5 font-mono text-xs font-bold text-[var(--color-success)]">
                      ${item.final_payout || item.recommended_payout || '—'}
                    </td>
                    <td className="p-3.5">
                      <span className={statusPill(item.status)}>
                        {item.status === 'approved' ? (
                          <CheckCircle className="h-3 w-3" />
                        ) : item.status === 'rejected' ? (
                          <XCircle className="h-3 w-3" />
                        ) : (
                          <AlertTriangle className="h-3 w-3" />
                        )}
                        {item.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </td>
                    <td className="max-w-xs truncate p-3.5 text-xs text-[var(--color-fg-secondary)]">
                      {item.final_justification || item.recommendation_reasoning || '—'}
                    </td>
                    <td className="p-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => openDetail(item)}
                          className="btn btn-secondary btn-sm"
                          title="View full detail"
                        >
                          <Eye className="h-3.5 w-3.5" /> Review
                        </button>
                        {canDelete ? (
                          <button
                            onClick={() => setConfirmDeleteId(item.claim_id)}
                            className="btn btn-danger btn-sm"
                            title="Delete decided claim"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        ) : (
                          <button
                            className="btn btn-ghost btn-sm opacity-40"
                            disabled
                            title="Cannot delete until approve or deny"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {filteredItems.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-sm text-[var(--color-fg-tertiary)]">
                    No claims match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail / review modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/75 p-4 backdrop-blur-sm">
          <div className="soft-card animate-rise my-8 w-full max-w-3xl space-y-5 bg-[var(--color-panel)] p-6">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--color-border)] pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-[var(--color-fg)]" />
                  <h3 className="text-lg font-bold text-[var(--color-fg)]">
                    Claim Review: {selected.policy_number}
                  </h3>
                </div>
                <p className="mt-0.5 font-mono text-xs text-[var(--color-fg-tertiary)]">
                  {selected.claim_id}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={statusPill(selected.status)}>
                  {selected.status.replace('_', ' ').toUpperCase()}
                </span>
                <button
                  onClick={closeDetail}
                  className="text-[var(--color-fg-tertiary)] hover:text-[var(--color-fg)]"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Detail grid */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <DetailCard icon={<User className="h-4 w-4" />} label="User ID" value={selected.user_id || 'Unknown'} mono />
              <DetailCard
                icon={<Calendar className="h-4 w-4" />}
                label="Date of Loss"
                value={selected.date_of_loss}
                mono
              />
              <DetailCard
                icon={<DollarSign className="h-4 w-4" />}
                label="Requested Amount"
                value={`$${selected.claim_amount_requested}`}
                mono
              />
              <DetailCard
                icon={<DollarSign className="h-4 w-4" />}
                label="AI Recommended Payout"
                value={selected.recommended_payout ? `$${selected.recommended_payout}` : '—'}
                mono
              />
              <DetailCard
                icon={<DollarSign className="h-4 w-4" />}
                label="Deductible / Limit"
                value={`${selected.deductible_applied ? `$${selected.deductible_applied}` : '—'} / ${
                  selected.policy_limit ? `$${selected.policy_limit}` : '—'
                }`}
                mono
              />
              <DetailCard
                icon={<Calendar className="h-4 w-4" />}
                label="Submitted"
                value={selected.created_at ? selected.created_at.slice(0, 19).replace('T', ' ') : '—'}
                mono
              />
            </div>

            <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-recessed)] p-4">
              <span className="eyebrow">Incident Description</span>
              <p className="mt-1 text-sm leading-relaxed text-[var(--color-fg)]">
                {selected.incident_description}
              </p>
            </div>

            {/* AI decision + citations */}
            <div className="space-y-2 rounded-xl border border-[var(--color-border-light)] bg-[var(--color-recessed)] p-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[var(--color-fg-secondary)]" />
                <span className="eyebrow">AI Decision & Justification (with citations)</span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-fg)]">
                {selected.ai_justification || selected.recommendation_reasoning || 'No AI justification.'}
              </p>
              {selected.citations && selected.citations.length > 0 && (
                <ul className="mt-2 space-y-1.5 border-t border-[var(--color-border)] pt-2">
                  {selected.citations.map((c, i) => (
                    <li key={i} className="flex gap-2 text-xs text-[var(--color-fg-secondary)]">
                      <Quote className="mt-0.5 h-3 w-3 shrink-0 text-[var(--color-fg-tertiary)]" />
                      <span>
                        <span className="font-mono text-[var(--color-fg)]">
                          {c.policy_id || ''}
                          {c.page ? ` p.${c.page}` : ''}
                          {c.section ? ` · ${c.section}` : ''}
                        </span>
                        {': '}
                        {String(c.text_preview || c.text || '').slice(0, 200)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Editable fields (only while undecided) */}
            {UNDECIDED.has(selected.status) ? (
              <div className="space-y-4 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                <span className="eyebrow">Adjuster Edits (applied on decision)</span>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
                      Payout Amount ($) — AI set ${selected.recommended_payout || '0.00'}
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="karen-input font-mono text-sm"
                      value={editPayout}
                      onChange={(e) => setEditPayout(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
                      Adjuster Notes
                    </label>
                    <input
                      type="text"
                      className="karen-input text-sm"
                      placeholder="Optional audit notes…"
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
                    Justification — edit the AI answer before approving
                  </label>
                  <textarea
                    rows={5}
                    className="karen-input min-h-[110px] py-2 text-sm"
                    value={editJustification}
                    onChange={(e) => setEditJustification(e.target.value)}
                  />
                </div>

                <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[var(--color-border)] pt-3">
                  <button onClick={closeDetail} className="btn btn-ghost btn-sm" disabled={busy}>
                    Close
                  </button>
                  <button
                    onClick={() => sendDecision('reject')}
                    className="btn btn-danger btn-sm"
                    disabled={busy}
                  >
                    <XCircle className="h-3.5 w-3.5" /> Deny
                  </button>
                  <button
                    onClick={() => sendDecision('approve')}
                    className="btn btn-primary btn-sm"
                    disabled={busy}
                  >
                    <ShieldCheck className="h-3.5 w-3.5" /> Approve
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 rounded-xl border border-[var(--color-border-light)] bg-[var(--color-recessed)] p-4">
                <span className="eyebrow">Decision Taken</span>
                {selected.admin_justification && (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">
                      Adjuster-edited justification
                    </span>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-[var(--color-fg)]">
                      {selected.admin_justification}
                    </p>
                  </div>
                )}
                {selected.adjuster_notes && (
                  <div className="rounded-lg border border-[var(--color-border-light)] bg-[var(--color-bg-tertiary)] p-3">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-fg-tertiary)]">
                      Adjuster notes
                    </span>
                    <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">{selected.adjuster_notes}</p>
                  </div>
                )}
                <div className="flex justify-between pt-1">
                  <button onClick={closeDetail} className="btn btn-ghost btn-sm">
                    Close
                  </button>
                  {DECIDED.has(selected.status) ? (
                    <button
                      onClick={() => setConfirmDeleteId(selected.claim_id)}
                      className="btn btn-danger btn-sm"
                    >
                      <Trash2 className="h-3.5 w-3.5" /> Delete Claim
                    </button>
                  ) : (
                    <span className="self-center text-xs italic text-[var(--color-fg-tertiary)]">
                      Decision required before delete
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="soft-card animate-rise w-full max-w-md space-y-4 bg-[var(--color-panel)] p-6">
            <div className="flex items-center gap-2">
              <Trash2 className="h-5 w-5 text-red-400" />
              <h3 className="text-base font-bold text-[var(--color-fg)]">Delete Claim?</h3>
            </div>
            <p className="text-sm text-[var(--color-fg-secondary)]">
              This permanently deletes claim{' '}
              <span className="font-mono text-xs">{confirmDeleteId}</span>. This action cannot be
              undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setConfirmDeleteId(null)} className="btn btn-ghost btn-sm">
                Cancel
              </button>
              <button
                onClick={() => handleDelete(confirmDeleteId)}
                className="btn btn-danger btn-sm"
              >
                <Trash2 className="h-3.5 w-3.5" /> Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const DetailCard: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}> = ({ icon, label, value, mono }) => (
  <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-4">
    <div className="flex items-center gap-1.5 text-xs font-medium text-[var(--color-fg-secondary)]">
      {icon} {label}
    </div>
    <div className={`mt-1 text-sm font-semibold text-[var(--color-fg)] ${mono ? 'font-mono' : ''}`}>
      {value}
    </div>
  </div>
);
