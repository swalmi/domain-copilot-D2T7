import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  CheckCircle,
  XCircle,
  Edit3,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface ApprovalItem {
  claim_id: string;
  policy_number: string;
  status: 'pending_approval' | 'approved' | 'rejected';
  claim_amount_requested: string;
  recommended_payout: string;
  recommendation_reasoning: string;
  created_at: string;
}

export const ApprovalsQueue: React.FC = () => {
  const { user } = useAuth();

  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [editingItem, setEditingItem] = useState<ApprovalItem | null>(null);
  const [overridePayout, setOverridePayout] = useState<string>('');
  const [adjusterNotes, setAdjusterNotes] = useState<string>('');

  useEffect(() => {
    fetchApprovals();
  }, [user?.role]);

  const fetchApprovals = async () => {
    try {
      const res = await fetch('/approvals');
      if (res.ok) {
        const data = await res.json();
        setItems(data);
      } else {
        loadDefaultMockData();
      }
    } catch {
      loadDefaultMockData();
    }
  };

  const loadDefaultMockData = () => {
    setItems([
      {
        claim_id: 'c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c',
        policy_number: 'POL-1001',
        status: 'pending_approval',
        claim_amount_requested: '4500.00',
        recommended_payout: '4000.00',
        recommendation_reasoning: 'Water pipe leak dwelling damage. Deductible of $500.00 applied.',
        created_at: '2026-08-31T01:00:00Z',
      },
      {
        claim_id: '88776655-4433-2211-00ff-aabbccddeeff',
        policy_number: 'POL-2004',
        status: 'pending_approval',
        claim_amount_requested: '18500.00',
        recommended_payout: '17500.00',
        recommendation_reasoning: 'Roof windstorm damage claim. Deductible of $1,000.00 applied.',
        created_at: '2026-08-31T01:15:00Z',
      },
      {
        claim_id: '99001122-3344-5566-7788-99aabbccddee',
        policy_number: 'POL-3009',
        status: 'approved',
        claim_amount_requested: '3200.00',
        recommended_payout: '2700.00',
        recommendation_reasoning: 'Kitchen cabinet water damage approved by adjuster.',
        created_at: '2026-08-30T18:30:00Z',
      },
    ]);
  };

  const handleApprove = async (id: string) => {
    try {
      await fetch(`/approvals/${id}/approve`, { method: 'POST' });
    } catch {
      // Mock update
    }
    setItems((prev) =>
      prev.map((item) => (item.claim_id === id ? { ...item, status: 'approved' } : item))
    );
  };

  const handleReject = async (id: string) => {
    try {
      await fetch(`/approvals/${id}/reject`, { method: 'POST' });
    } catch {
      // Mock update
    }
    setItems((prev) =>
      prev.map((item) => (item.claim_id === id ? { ...item, status: 'rejected' } : item))
    );
  };

  const handleOpenEdit = (item: ApprovalItem) => {
    setEditingItem(item);
    setOverridePayout(item.recommended_payout);
    setAdjusterNotes('Adjusted payout following detailed loss inspection review.');
  };

  const handleSaveEditAndApprove = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem) return;

    try {
      await fetch(`/approvals/${editingItem.claim_id}/edit-and-approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          override_payout: overridePayout,
          adjuster_notes: adjusterNotes,
        }),
      });
    } catch {
      // Mock update
    }

    setItems((prev) =>
      prev.map((item) =>
        item.claim_id === editingItem.claim_id
          ? { ...item, status: 'approved', recommended_payout: overridePayout }
          : item
      )
    );
    setEditingItem(null);
  };

  const filteredItems = items.filter((item) => {
    if (filter === 'pending') return item.status === 'pending_approval';
    if (filter === 'approved') return item.status === 'approved';
    if (filter === 'rejected') return item.status === 'rejected';
    return true;
  });

  return (
    <div className="animate-rise space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="eyebrow">Human-in-the-Loop Gate</span>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-[var(--color-fg)]">
            Adjuster Approval Queue
          </h2>
          <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
            Review, approve, deny, or override AI-generated claim payout recommendations.
          </p>
        </div>

        {/* Filter Pills */}
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

      {/* Approval Queue Table */}
        <div className="soft-card overflow-hidden">
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--color-recessed)] text-xs font-medium text-[var(--color-fg-secondary)] border-b border-[var(--color-border)]">
                <tr>
                  <th className="p-3.5">Policy Number</th>
                  <th className="p-3.5">Requested</th>
                  <th className="p-3.5">Recommended Payout</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">Reasoning</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {filteredItems.map((item) => (
                  <tr key={item.claim_id} className="hover:bg-[var(--color-bg-tertiary)]">
                    <td className="p-3.5 font-mono text-xs font-semibold text-[var(--color-fg)]">
                      {item.policy_number}
                    </td>
                    <td className="p-3.5 font-mono text-xs text-[var(--color-fg-secondary)]">
                      ${item.claim_amount_requested}
                    </td>
                    <td className="p-3.5 font-mono text-xs font-bold text-[var(--color-success)]">
                      ${item.recommended_payout}
                    </td>
                    <td className="p-3.5">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                          item.status === 'approved'
                            ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                            : item.status === 'rejected'
                            ? 'bg-red-500/10 text-red-400 border border-red-500/30'
                            : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                        }`}
                      >
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
                    <td className="p-3.5 text-xs text-[var(--color-fg-secondary)] max-w-xs truncate">
                      {item.recommendation_reasoning}
                    </td>
                    <td className="p-3.5 text-right">
                      {item.status === 'pending_approval' ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleApprove(item.claim_id)}
                            className="btn btn-primary btn-sm"
                            title="Approve Recommendation"
                          >
                            <ShieldCheck className="h-3.5 w-3.5" /> Approve
                          </button>
                          <button
                            onClick={() => handleOpenEdit(item)}
                            className="btn btn-secondary btn-sm"
                            title="Edit & Approve"
                          >
                            <Edit3 className="h-3.5 w-3.5" /> Override
                          </button>
                          <button
                            onClick={() => handleReject(item.claim_id)}
                            className="btn btn-danger btn-sm"
                            title="Reject Claim"
                          >
                            <XCircle className="h-3.5 w-3.5" /> Reject
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--color-fg-tertiary)] italic">Finalized</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      {/* Edit & Approve Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="soft-card max-w-md w-full p-6 space-y-4 animate-rise bg-[var(--color-panel)]">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
              <h3 className="text-base font-bold text-[var(--color-fg)]">
                Override & Approve Payout
              </h3>
              <button
                onClick={() => setEditingItem(null)}
                className="text-[var(--color-fg-tertiary)] hover:text-[var(--color-fg)]"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveEditAndApprove} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
                  Override Payout Amount ($)
                </label>
                <input
                  type="number"
                  step="0.01"
                  className="karen-input font-mono text-sm"
                  value={overridePayout}
                  onChange={(e) => setOverridePayout(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
                  Adjuster Audit Notes
                </label>
                <textarea
                  rows={3}
                  className="karen-input min-h-[80px] py-2"
                  value={adjusterNotes}
                  onChange={(e) => setAdjusterNotes(e.target.value)}
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingItem(null)}
                  className="btn btn-ghost btn-sm"
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm">
                  <FileText className="h-3.5 w-3.5" /> Save & Approve Payout
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
