import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Zap,
  ShieldCheck,
  Ban,
  Clock,
  CheckCircle2,
  FileCheck,
  Circle,
  RefreshCw,
  XCircle,
  Trash2,
  AlertTriangle,
} from 'lucide-react';

interface ClaimRecord {
  claim_id: string;
  correlation_id?: string | null;
  user_id?: string | null;
  policy_number: string;
  date_of_loss: string;
  incident_description: string;
  claim_amount_requested: string;
  status: string;
  pipeline_stage?: string | null;
  calculated_payout?: string | null;
  deductible_applied?: string | null;
  policy_limit?: string | null;
  adjusted_payout?: string | null;
  final_payout?: string | null;
  recommendation?: string | null;
  reasoning_text?: string | null;
  final_justification?: string | null;
  citations?: Array<Record<string, unknown>>;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

type StageState = 'pending' | 'running' | 'passed' | 'failed';
interface StageInfo {
  id: string;
  label: string;
  desc: string;
  state: StageState;
  detail?: string;
}

const buildStages = (policy: string): StageInfo[] => [
  {
    id: 'understanding',
    label: 'Understanding your claim',
    desc: 'Parsing incident details and requested amount',
  },
  {
    id: 'reading_policy',
    label: `Reading policy ${policy}`,
    desc: 'Retrieving and scoring coverage sections from the policy corpus',
  },
  {
    id: 'matching',
    label: 'Matched / Not matched',
    desc: 'Evaluating coverage confidence against the incident',
  },
  {
    id: 'building_report',
    label: 'Building your report',
    desc: 'Exclusion analysis, payout calculation, and citations',
  },
  {
    id: 'done',
    label: 'Report ready',
    desc: 'Review the AI report — adjuster decides in the approval queue',
  },
];

const REPORT_STATUSES = new Set([
  'report_ready',
  'pending_approval',
  'approved',
  'rejected',
  'refused',
  'cancelled',
  'failed',
]);

function stagesFromClaim(claim: ClaimRecord, policy: string): StageInfo[] {
  const stages = buildStages(policy);
  const stage = claim.pipeline_stage;
  const status = claim.status;

  const markUpTo = (idx: number, current: StageState, detail?: string) => {
    stages.forEach((s, i) => {
      if (i < idx) s.state = 'passed';
      else if (i === idx) {
        s.state = current;
        if (detail) s.detail = detail;
      } else s.state = 'pending';
    });
  };

  if (status === 'failed') {
    const idx =
      stage === 'building_report' ? 3 : stage === 'matched' || stage === 'not_matched' ? 2 : stage === 'reading_policy' ? 1 : 0;
    markUpTo(idx, 'failed', claim.error_message || 'Step failed');
    return stages;
  }

  switch (stage) {
    case 'understanding':
    case undefined:
    case null:
      markUpTo(0, status === 'submitted' || status === 'processing' ? 'running' : 'pending');
      break;
    case 'reading_policy':
      markUpTo(1, 'running');
      break;
    case 'matched':
      markUpTo(2, 'passed', 'Matched — coverage sections found');
      break;
    case 'not_matched':
      markUpTo(2, 'passed', 'Not matched — no applicable coverage sections');
      break;
    case 'building_report':
      markUpTo(3, 'running');
      break;
    case 'done':
      stages.forEach((s) => (s.state = 'passed'));
      break;
    default:
      markUpTo(0, 'running');
  }

  // Terminal statuses: freeze the pipeline as complete (or refused).
  if (REPORT_STATUSES.has(status) && status !== 'failed') {
    if (status === 'refused') {
      stages.forEach((s, i) => (s.state = i <= 2 ? 'passed' : 'pending'));
      stages[2].detail = 'Not matched — claim refused by coverage check';
    } else {
      stages.forEach((s) => (s.state = 'passed'));
    }
  }
  return stages;
}

const statusPill = (status: string) => {
  const base =
    'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold';
  if (status === 'approved')
    return `${base} border border-green-500/30 bg-green-500/10 text-green-400`;
  if (status === 'rejected' || status === 'cancelled' || status === 'refused' || status === 'failed')
    return `${base} border border-red-500/30 bg-red-500/10 text-red-400`;
  if (status === 'pending_approval')
    return `${base} border border-amber-500/30 bg-amber-500/10 text-amber-400`;
  return `${base} border border-[var(--color-border-light)] bg-[var(--color-bg-tertiary)] text-[var(--color-fg-secondary)]`;
};

export const ClaimAdjudication: React.FC = () => {
  const [policyNumber, setPolicyNumber] = useState('ISO-PP-00-01');
  const [dateOfLoss, setDateOfLoss] = useState('2026-08-15');
  const [claimAmount, setClaimAmount] = useState('4500.00');
  const [incidentDescription, setIncidentDescription] = useState(
    'Electrical surge damaged kitchen appliances during storm on August 15.'
  );

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ClaimRecord | null>(null);
  const [stages, setStages] = useState<StageInfo[] | null>(null);
  const [stepStatus, setStepStatus] = useState<string>('');
  const [myClaims, setMyClaims] = useState<ClaimRecord[]>([]);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string>('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadMyClaims = useCallback(async () => {
    try {
      const res = await fetch('/claims', { credentials: 'include' });
      if (res.ok) setMyClaims(await res.json());
    } catch {
      // offline — keep previous list
    }
  }, []);

  useEffect(() => {
    loadMyClaims();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadMyClaims]);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const handleCreateClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;

    setIsLoading(true);
    setResult(null);
    setActionError('');
    setStages(buildStages(policyNumber).map((s, i) => ({ ...s, state: i === 0 ? 'running' : 'pending' })));
    setStepStatus('Submitting claim to Celery task queue...');

    try {
      const res = await fetch('/claims', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          policy_number: policyNumber,
          date_of_loss: dateOfLoss,
          claim_amount_requested: claimAmount,
          incident_description: incidentDescription,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Submission failed (${res.status})`);
      }
      const data = await res.json();
      setStepStatus('Task queued (202 Accepted). Running multi-agent workflow...');
      pollClaimStatus(data.claim_id, policyNumber);
    } catch (err) {
      setIsLoading(false);
      setResult(null);
      setStages(null);
      setStepStatus(
        `Claim submission failed: ${err instanceof Error ? err.message : 'unknown error'}`
      );
    }
  };

  const pollClaimStatus = (claimId: string, policy: string) => {
    stopPolling();
    let attempts = 0;
    const maxAttempts = 120;
    pollRef.current = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch(`/claims/${claimId}`, { credentials: 'include' });
        if (res.ok) {
          const data: ClaimRecord = await res.json();
          setStages(stagesFromClaim(data, policy));
          if (REPORT_STATUSES.has(data.status)) {
            stopPolling();
            setResult(data);
            setIsLoading(false);
            setStepStatus(
              data.status === 'report_ready'
                ? 'Report ready — waiting for adjuster review.'
                : `Claim status: ${data.status.replace('_', ' ')}.`
            );
            loadMyClaims();
            return;
          }
          setStepStatus(
            `Status: ${data.status.toUpperCase()} — ${data.pipeline_stage || 'working'}…`
          );
        } else if (res.status === 404) {
          setStepStatus('Claim recorded; poll pending...');
        } else {
          setStepStatus(`Claim status check failed (${res.status}). Retrying...`);
        }
      } catch {
        // network hiccup — keep polling
      }
      if (attempts >= maxAttempts) {
        stopPolling();
        setIsLoading(false);
        setStepStatus('Adjudication still running. Refresh to see the latest result.');
      }
    }, 1500);
  };

  const handleDiscardReport = async () => {
    if (!result?.claim_id) return;
    if (!window.confirm('Discard this report? The claim will be cancelled and cannot be submitted.')) {
      return;
    }
    try {
      await fetch(`/claims/${result.claim_id}/cancel`, {
        method: 'POST',
        credentials: 'include',
      });
      setResult((prev) => (prev ? { ...prev, status: 'cancelled' } : prev));
      loadMyClaims();
    } catch {
      setActionError('Failed to cancel claim');
    }
  };

  const handleDeleteClaim = async (claimId: string) => {
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
      setMyClaims((prev) => prev.filter((c) => c.claim_id !== claimId));
      if (result?.claim_id === claimId) setResult(null);
      setConfirmDeleteId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete claim');
      setConfirmDeleteId(null);
    }
  };

  const openClaim = async (claimId: string) => {
    try {
      const res = await fetch(`/claims/${claimId}`, { credentials: 'include' });
      if (res.ok) {
        const data: ClaimRecord = await res.json();
        setResult(data);
        setStages(stagesFromClaim(data, data.policy_number));
        setIsLoading(false);
        setStepStatus('');
      }
    } catch {
      // ignore
    }
  };

  const showPipeline = isLoading || (result && !REPORT_STATUSES.has(result.status));
  const reportReady = result?.status === 'report_ready';
  const waitingApproval = result?.status === 'pending_approval';
  const decided =
    result &&
    ['approved', 'rejected', 'refused', 'cancelled', 'failed'].includes(result.status);

  return (
    <div className="animate-rise space-y-6">
      <div>
        <span className="eyebrow">Human-in-the-Loop Adjudication</span>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-[var(--color-fg)]">
          Claim Adjudication Workflow
        </h2>
        <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
          Submit a claim and review the AI report. Decisions stay with insurer staff in the approval queue.
        </p>
      </div>

      {/* Claim Submission Form */}
      <form onSubmit={handleCreateClaim} className="soft-card p-5 space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Policy Number
            </label>
            <input
              type="text"
              className="karen-input font-mono text-xs"
              value={policyNumber}
              onChange={(e) => setPolicyNumber(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Date of Loss
            </label>
            <input
              type="date"
              className="karen-input font-mono text-xs"
              value={dateOfLoss}
              onChange={(e) => setDateOfLoss(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Requested Payout ($)
            </label>
            <input
              type="number"
              step="0.01"
              className="karen-input font-mono text-xs"
              value={claimAmount}
              onChange={(e) => setClaimAmount(e.target.value)}
              required
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
            Incident Description
          </label>
          <textarea
            rows={3}
            className="karen-input min-h-[75px] py-2"
            value={incidentDescription}
            onChange={(e) => setIncidentDescription(e.target.value)}
            required
          />
        </div>

        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-[var(--color-fg-tertiary)]">
            Returns HTTP 202 and streams pipeline progress while agents run.
          </span>
          <button type="submit" disabled={isLoading} className="btn btn-primary">
            <Zap className="h-4 w-4" /> Run Adjudication
          </button>
        </div>
      </form>

      {actionError && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {actionError}
        </div>
      )}

      {/* Claim Pipeline (ingestion-style) */}
      {showPipeline && stages && (
        <div className="soft-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <span className="eyebrow">Claim Pipeline</span>
            {isLoading ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--color-fg-secondary)]">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Processing…
              </span>
            ) : (
              <span className="text-xs text-[var(--color-fg-tertiary)]">
                {stages.some((s) => s.state === 'failed')
                  ? 'Failed'
                  : stages.every((s) => s.state === 'passed')
                    ? 'All stages passed'
                    : 'In progress'}
              </span>
            )}
          </div>

          <ol className="space-y-0">
            {stages.map((stage, i) => {
              const isLast = i === stages.length - 1;
              return (
                <li key={stage.id} className="relative flex gap-3 pb-0">
                  {!isLast && (
                    <span
                      className={`absolute left-[15px] top-8 bottom-0 w-px ${
                        stage.state === 'passed' ? 'bg-emerald-500/40' : 'bg-[var(--color-border)]'
                      }`}
                    />
                  )}
                  <div
                    className="z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-[var(--color-bg-secondary)]"
                    style={{
                      borderColor:
                        stage.state === 'passed'
                          ? 'rgba(16,185,129,0.4)'
                          : stage.state === 'failed'
                            ? 'rgba(239,68,68,0.4)'
                            : stage.state === 'running'
                              ? 'var(--color-border-light)'
                              : 'var(--color-border)',
                    }}
                  >
                    {stage.state === 'passed' && <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400" />}
                    {stage.state === 'failed' && <XCircle className="h-4.5 w-4.5 text-red-400" />}
                    {stage.state === 'running' && (
                      <RefreshCw className="h-4 w-4 animate-spin text-[var(--color-accent)]" />
                    )}
                    {stage.state === 'pending' && <Circle className="h-3.5 w-3.5 text-[var(--color-fg-tertiary)]" />}
                  </div>
                  <div className="pb-4 pt-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold" style={{ color: 'var(--color-fg)' }}>
                        {stage.label}
                      </span>
                      {stage.state === 'running' && (
                        <span className="rounded-full border border-[var(--color-border-light)] bg-[var(--color-bg-tertiary)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[var(--color-accent)]">
                          Running
                        </span>
                      )}
                      {stage.state === 'passed' && (
                        <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-400">
                          Passed
                        </span>
                      )}
                      {stage.state === 'failed' && (
                        <span className="rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-red-400">
                          Failed
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--color-fg-secondary)]">{stage.desc}</p>
                    {stage.detail && (
                      <p className="mt-1 font-mono text-[11px] text-[var(--color-fg-tertiary)]">{stage.detail}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
          {stepStatus && (
            <p className="mt-1 border-t border-[var(--color-border)] pt-3 font-mono text-xs text-[var(--color-fg-secondary)]">
              {stepStatus}
            </p>
          )}
        </div>
      )}

      {/* Report Card with Submit / Discard CTAs */}
      {result && reportReady && (
        <div className="soft-card p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] pb-4">
            <div>
              <div className="flex items-center gap-2">
                <FileCheck className="h-5 w-5 text-[var(--color-fg)]" />
                <h3 className="text-lg font-bold text-[var(--color-fg)]">
                  Adjudication Report: {result.policy_number}
                </h3>
              </div>
              <p className="mt-0.5 font-mono text-xs text-[var(--color-fg-tertiary)]">
                Claim ID: {result.claim_id}
                {result.correlation_id ? ` · Correlation: ${result.correlation_id}` : ''}
              </p>
            </div>
            <span className={statusPill(result.status)}>
              <Clock className="h-3.5 w-3.5" /> REPORT READY
            </span>
          </div>

          <ReportBody claim={result} />

          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[var(--color-border)] pt-4">
            <button onClick={handleDiscardReport} className="btn btn-danger">
              <Ban className="h-4 w-4" /> Discard Report
            </button>
          </div>
          <p className="text-right text-xs text-[var(--color-fg-tertiary)]">
            Adjusters review reports in the approval queue. Clients cannot approve claims.
          </p>
        </div>
      )}

      {/* Waiting for approval */}
      {result && waitingApproval && (
        <div className="soft-card p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] pb-4">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-amber-400" />
              <h3 className="text-lg font-bold text-[var(--color-fg)]">
                Waiting for Adjuster Approval
              </h3>
            </div>
            <span className={statusPill(result.status)}>
              <Clock className="h-3.5 w-3.5" /> PENDING APPROVAL
            </span>
          </div>
          <p className="text-sm text-[var(--color-fg-secondary)]">
            Your claim <span className="font-mono">{result.claim_id}</span> on policy{' '}
            <span className="font-mono">{result.policy_number}</span> has been submitted. An adjuster
            will review the AI report, optionally adjust the payout or justification, then approve or
            deny it. The decision will appear here.
          </p>
          <ReportBody claim={result} />
        </div>
      )}

      {/* Decided result */}
      {result && decided && (
        <div className="soft-card p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] pb-4">
            <div>
              <div className="flex items-center gap-2">
                <FileCheck className="h-5 w-5 text-[var(--color-fg)]" />
                <h3 className="text-lg font-bold text-[var(--color-fg)]">
                  Claim Result: {result.policy_number}
                </h3>
              </div>
              <p className="mt-0.5 font-mono text-xs text-[var(--color-fg-tertiary)]">
                Claim ID: {result.claim_id}
              </p>
            </div>
            <span className={statusPill(result.status)}>
              {result.status === 'approved' ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Ban className="h-3.5 w-3.5" />
              )}
              {result.status.toUpperCase()}
            </span>
          </div>

          <ReportBody claim={result} showAdjuster={result.status === 'approved' || result.status === 'rejected'} />

          <div className="flex justify-end border-t border-[var(--color-border)] pt-4">
            <button onClick={() => setConfirmDeleteId(result.claim_id)} className="btn btn-danger btn-sm">
              <Trash2 className="h-3.5 w-3.5" /> Delete Claim
            </button>
          </div>
        </div>
      )}

      {/* My Claims */}
      <div className="soft-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] p-4">
          <span className="eyebrow">My Claims</span>
          <span className="text-xs text-[var(--color-fg-tertiary)]">{myClaims.length} Claims</span>
        </div>
        {myClaims.length === 0 ? (
          <p className="p-4 text-sm text-[var(--color-fg-tertiary)]">No claims yet — submit one above.</p>
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--color-border)] bg-[var(--color-recessed)] text-xs font-medium text-[var(--color-fg-secondary)]">
                <tr>
                  <th className="p-3.5">Policy</th>
                  <th className="p-3.5">Requested</th>
                  <th className="p-3.5">Payout</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">Date</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {myClaims.map((c) => (
                  <tr key={c.claim_id} className="hover:bg-[var(--color-bg-tertiary)]">
                    <td className="p-3.5 font-mono text-xs font-semibold">{c.policy_number}</td>
                    <td className="p-3.5 font-mono text-xs">${c.claim_amount_requested}</td>
                    <td className="p-3.5 font-mono text-xs">
                      {c.final_payout ? `$${c.final_payout}` : '—'}
                    </td>
                    <td className="p-3.5">
                      <span className={statusPill(c.status).replace('px-3 py-1', 'px-2.5 py-0.5')}>
                        {c.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </td>
                    <td className="p-3.5 font-mono text-xs text-[var(--color-fg-tertiary)]">
                      {c.created_at ? c.created_at.slice(0, 10) : '—'}
                    </td>
                    <td className="p-3.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => openClaim(c.claim_id)} className="btn btn-secondary btn-sm">
                          <FileCheck className="h-3.5 w-3.5" /> View
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(c.claim_id)}
                          className="btn btn-danger btn-sm"
                          title="Delete claim"
                        >
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete confirmation */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
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
                onClick={() => handleDeleteClaim(confirmDeleteId)}
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

/** Shared report body: metric tiles, AI justification, citations, adjuster edits. */
const ReportBody: React.FC<{ claim: ClaimRecord; showAdjuster?: boolean }> = ({
  claim,
  showAdjuster,
}) => (
  <>
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
      <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-4">
        <span className="text-xs font-medium text-[var(--color-fg-secondary)]">Requested Amount</span>
        <div className="mt-1 font-mono text-xl font-bold text-[var(--color-fg)]">
          ${claim.claim_amount_requested}
        </div>
      </div>
      <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-4">
        <span className="text-xs font-medium text-[var(--color-fg-secondary)]">Deductible Applied</span>
        <div className="mt-1 font-mono text-xl font-bold text-[var(--color-danger)]">
          {claim.deductible_applied ? `-$${claim.deductible_applied}` : '—'}
        </div>
      </div>
      <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-4">
        <span className="text-xs font-medium text-[var(--color-fg-secondary)]">Policy Limit</span>
        <div className="mt-1 font-mono text-xl font-bold text-[var(--color-fg-secondary)]">
          {claim.policy_limit ? `$${claim.policy_limit}` : '—'}
        </div>
      </div>
      <div className="rounded-xl border border-[var(--color-accent)] bg-[var(--color-active-bg)] p-4">
        <span className="text-xs font-medium text-[var(--color-fg)]">
          {claim.adjusted_payout ? 'Final Payout (adjusted)' : 'AI Recommended Payout'}
        </span>
        <div className="mt-1 font-mono text-xl font-bold text-[var(--color-success)]">
          {claim.final_payout || claim.calculated_payout ? `$${claim.final_payout || claim.calculated_payout}` : '—'}
        </div>
        {claim.adjusted_payout && claim.calculated_payout && claim.adjusted_payout !== claim.calculated_payout && (
          <div className="mt-0.5 font-mono text-[11px] text-[var(--color-fg-tertiary)]">
            AI suggested ${claim.calculated_payout}
          </div>
        )}
      </div>
    </div>

    <div className="space-y-2 rounded-xl border border-[var(--color-border-light)] bg-[var(--color-recessed)] p-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-[var(--color-fg-secondary)]" />
        <span className="eyebrow">AI Justification & Recommendation</span>
      </div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-fg)]">
        {claim.final_justification || claim.recommendation || claim.reasoning_text || 'No recommendation generated.'}
      </p>
      {showAdjuster && claim.admin_justification && claim.admin_justification !== claim.reasoning_text && (
        <div className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">
            Adjuster-edited justification
          </span>
          <p className="mt-1 whitespace-pre-wrap text-sm text-[var(--color-fg)]">{claim.admin_justification}</p>
        </div>
      )}
      {showAdjuster && claim.adjuster_notes && (
        <div className="mt-1 rounded-lg border border-[var(--color-border-light)] bg-[var(--color-bg-tertiary)] p-3">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-fg-tertiary)]">
            Adjuster notes
          </span>
          <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">{claim.adjuster_notes}</p>
        </div>
      )}
    </div>

    {claim.citations && claim.citations.length > 0 && (
      <div className="space-y-2 rounded-xl border border-[var(--color-border-light)] bg-[var(--color-recessed)] p-4">
        <span className="eyebrow">Citations ({claim.citations.length})</span>
        <ul className="space-y-1.5">
          {claim.citations.map((c, i) => (
            <li key={i} className="text-xs text-[var(--color-fg-secondary)]">
              <span className="font-mono text-[var(--color-fg)]">
                {String(c.policy_id || '')}
                {c.page ? ` p.${c.page}` : ''}
                {c.section ? ` · ${c.section}` : ''}
              </span>
              {': '}
              {String(c.text_preview || c.text || '').slice(0, 180)}
              {String(c.text_preview || c.text || '').length > 180 ? '…' : ''}
            </li>
          ))}
        </ul>
      </div>
    )}
  </>
);
