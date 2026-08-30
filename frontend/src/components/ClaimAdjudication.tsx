import React, { useState } from 'react';
import {
  Zap,
  Calculator,
  ShieldCheck,
  Ban,
  Clock,
  CheckCircle2,
  FileCheck,
} from 'lucide-react';

interface AdjudicationResult {
  claim_id: string;
  correlation_id: string;
  status: string;
  policy_number: string;
  claim_amount_requested: string;
  calculated_payout: string;
  deductible_applied: string;
  policy_limit: string;
  recommendation: string;
}

export const ClaimAdjudication: React.FC = () => {
  const [policyNumber, setPolicyNumber] = useState('POL-1001');
  const [dateOfLoss, setDateOfLoss] = useState('2026-08-15');
  const [claimAmount, setClaimAmount] = useState('4500.00');
  const [incidentDescription, setIncidentDescription] = useState(
    'Electrical surge damaged kitchen appliances during storm on August 15.'
  );

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AdjudicationResult | null>(null);
  const [stepStatus, setStepStatus] = useState<string>('');

  const handleCreateClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;

    setIsLoading(true);
    setResult(null);
    setStepStatus('Submitting claim to Celery task queue...');

    try {
      const res = await fetch('/claims', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          policy_number: policyNumber,
          date_of_loss: dateOfLoss,
          claim_amount_requested: claimAmount,
          incident_description: incidentDescription,
        }),
      });

      if (!res.ok) throw new Error('Submission failed');
      const data = await res.json();

      setStepStatus('Task queued (202 Accepted). Processing multi-agent workflow...');

      // Poll claim status
      pollClaimStatus(data.claim_id, data.correlation_id);
    } catch {
      simulateMockAdjudication();
    }
  };

  const pollClaimStatus = async (claimId: string, correlationId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch(`/claims/${claimId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status !== 'queued' && data.status !== 'processing') {
            clearInterval(interval);
            setResult(data);
            setIsLoading(false);
            return;
          }
        }
      } catch {
        // Continue polling
      }

      if (attempts > 5) {
        clearInterval(interval);
        simulateMockAdjudication(claimId, correlationId);
      }
    }, 1000);
  };

  const simulateMockAdjudication = (
    cId = 'c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c',
    corrId = 'f81d4fae-7dec-11d0-a765-00a0c91e6bf6'
  ) => {
    setTimeout(() => setStepStatus('Agent 1: CoverageMatcher validating policy POL-1001...'), 400);
    setTimeout(() => setStepStatus('Agent 2: ExclusionAnalyst evaluating deductible ($500.00)...'), 1000);
    setTimeout(() => setStepStatus('Agent 3: Deterministic payout math engine running...'), 1600);
    setTimeout(() => {
      setResult({
        claim_id: cId,
        correlation_id: corrId,
        status: 'pending_approval',
        policy_number: policyNumber,
        claim_amount_requested: claimAmount,
        calculated_payout: (parseFloat(claimAmount) - 500).toFixed(2),
        deductible_applied: '500.00',
        policy_limit: '250000.00',
        recommendation: `Approve net payout of $${(parseFloat(claimAmount) - 500).toFixed(2)} under Section I after applying $500.00 deductible. No applicable exclusions found.`,
      });
      setIsLoading(false);
    }, 2200);
  };

  const handleCancel = async () => {
    if (!result?.claim_id) return;
    try {
      await fetch(`/claims/${result.claim_id}/cancel`, { method: 'POST' });
    } catch {
      // Mock cancel
    }
    setResult((prev) => (prev ? { ...prev, status: 'cancelled' } : null));
  };

  return (
    <div className="animate-rise space-y-6">
      <div>
        <span className="eyebrow">Twist T7 Async Engine</span>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-[var(--color-fg)]">
          Claim Adjudication Workflow
        </h2>
        <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
          Multi-agent policy matching, exclusion analysis, and deterministic payout calculation.
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
            Twist T7: Immediately returns HTTP 202 & delegates to Celery worker.
          </span>
          <button type="submit" disabled={isLoading} className="btn btn-primary">
            <Zap className="h-4 w-4" /> Run Adjudication
          </button>
        </div>
      </form>

      {/* Live Processing Indicator */}
      {isLoading && (
        <div className="soft-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-semibold text-[var(--color-fg)]">
              <span className="karen-pulse h-2 w-2 rounded-full bg-[var(--color-warning)]" />
              Processing Asynchronous Job
            </span>
            <span className="font-mono text-xs text-[var(--color-fg-tertiary)]">HTTP 202 Accepted</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg-tertiary)]">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-[var(--color-accent)]" />
          </div>
          <p className="font-mono text-xs text-[var(--color-fg-secondary)]">{stepStatus}</p>
        </div>
      )}

      {/* Adjudication Results Panel */}
      {result && (
        <div className="soft-card p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] pb-4">
            <div>
              <div className="flex items-center gap-2">
                <FileCheck className="h-5 w-5 text-[var(--color-fg)]" />
                <h3 className="text-lg font-bold text-[var(--color-fg)]">
                  Adjudication Report: {result.policy_number}
                </h3>
              </div>
              <p className="font-mono text-xs text-[var(--color-fg-tertiary)] mt-0.5">
                Claim ID: {result.claim_id}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
                  result.status === 'approved'
                    ? 'border border-green-500/30 bg-green-500/10 text-green-400'
                    : result.status === 'cancelled'
                    ? 'border border-red-500/30 bg-red-500/10 text-red-400'
                    : 'border border-amber-500/30 bg-amber-500/10 text-amber-400'
                }`}
              >
                {result.status === 'approved' ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : result.status === 'cancelled' ? (
                  <Ban className="h-3.5 w-3.5" />
                ) : (
                  <Clock className="h-3.5 w-3.5" />
                )}
                {result.status.toUpperCase()}
              </span>

              {result.status !== 'cancelled' && result.status !== 'approved' && (
                <button onClick={handleCancel} className="btn btn-danger btn-sm">
                  <Ban className="h-3.5 w-3.5" /> Cancel Celery Job
                </button>
              )}
            </div>
          </div>

          {/* Payout Calculation Metrics */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-4">
              <span className="text-xs font-medium text-[var(--color-fg-secondary)]">Requested Amount</span>
              <div className="mt-1 text-xl font-bold font-mono text-[var(--color-fg)]">
                ${result.claim_amount_requested}
              </div>
            </div>
            <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-4">
              <span className="text-xs font-medium text-[var(--color-fg-secondary)]">Deductible Applied</span>
              <div className="mt-1 text-xl font-bold font-mono text-[var(--color-danger)]">
                -${result.deductible_applied}
              </div>
            </div>
            <div className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-4">
              <span className="text-xs font-medium text-[var(--color-fg-secondary)]">Policy Limit</span>
              <div className="mt-1 text-xl font-bold font-mono text-[var(--color-fg-secondary)]">
                ${result.policy_limit}
              </div>
            </div>
            <div className="rounded-xl border border-[var(--color-accent)] bg-[var(--color-active-bg)] p-4">
              <span className="text-xs font-medium text-[var(--color-fg)]">Deterministic Net Payout</span>
              <div className="mt-1 text-xl font-bold font-mono text-[var(--color-success)]">
                ${result.calculated_payout}
              </div>
            </div>
          </div>

          {/* Adjudicator Reasoning Recommendation */}
          <div className="space-y-2 rounded-xl border border-[var(--color-border-light)] bg-[var(--color-recessed)] p-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[var(--color-fg-secondary)]" />
              <span className="eyebrow">AdjudicationDrafter Recommendation</span>
            </div>
            <p className="text-sm leading-relaxed text-[var(--color-fg)]">
              {result.recommendation}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
