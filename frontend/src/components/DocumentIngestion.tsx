import React, { useEffect, useState } from 'react';
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  XCircle,
  Circle,
  Trash2,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface IngestedDocument {
  id: string;
  filename: string;
  policy_id: string | null;
  status: string;
  created_at: string;
}

type StageState = 'pending' | 'running' | 'passed' | 'failed';

interface StageInfo {
  id: string;
  label: string;
  desc: string;
  state: StageState;
  detail?: string;
}

const INGESTION_STAGES: { id: string; label: string; desc: string }[] = [
  { id: 'parsing', label: 'Parsing', desc: 'Reading the document' },
  { id: 'chunking', label: 'Chunking', desc: 'Splitting the document into sections' },
  { id: 'titling', label: 'Section Linking', desc: 'Attaching section titles to chunks' },
  { id: 'embedding', label: 'Embedding', desc: 'Generating vector embeddings' },
  { id: 'storing', label: 'Storing', desc: 'Saving chunks to the database' },
  { id: 'finalizing', label: 'Finalizing', desc: 'Marking the document as ingested' },
];

export const DocumentIngestion: React.FC = () => {
  const { user } = useAuth();
  const canManagePolicies = user?.role === 'corp';

  const [file, setFile] = useState<File | null>(null);
  const [policyId, setPolicyId] = useState('ISO-PP-00-01');
  const [policyType, setPolicyType] = useState('home');
  const [version, setVersion] = useState('v1');
  const [effectiveDate, setEffectiveDate] = useState('2026-01-01');

  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [pipeline, setPipeline] = useState<StageInfo[] | null>(null);
  const [documents, setDocuments] = useState<IngestedDocument[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [traceEvents, setTraceEvents] = useState<any[]>([]);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const res = await fetch('/documents', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      } else {
        loadMockDocuments();
      }
    } catch {
      loadMockDocuments();
    }
  };

  const loadMockDocuments = () => {
    setDocuments([
      {
        id: '9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d',
        filename: 'homeowners_policy_v1.pdf',
        policy_id: 'ISO-PP-00-01',
        status: 'ingested',
        created_at: '2026-08-31T00:00:00Z',
      },
      {
        id: '4a5b6c7d-8e9f-0a1b-2c3d-4e5f6a7b8c9d',
        filename: 'commercial_property_v2.docx',
        policy_id: 'POL-1002',
        status: 'ingested',
        created_at: '2026-08-30T14:20:00Z',
      },
    ]);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleDelete = async (doc: IngestedDocument) => {
    const label = doc.policy_id ?? doc.id;
    if (!window.confirm(`Remove policy ${label} from the knowledge base? This deletes its fingerprint and all related chunks.`)) {
      return;
    }
    setDeletingId(doc.id);
    try {
      const res = await fetch(`/documents/${doc.id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!res.ok) {
        throw new Error((await res.json().catch(() => null))?.detail ?? `Delete failed (${res.status})`);
      }
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
      setUploadMessage({ type: 'success', text: `Policy ${label} removed from the knowledge base.` });
    } catch (err) {
      setUploadMessage({ type: 'error', text: err instanceof Error ? err.message : 'Could not delete policy.' });
    } finally {
      setDeletingId(null);
    }
  };

  const resetPipeline = () => {
    setPipeline(
      INGESTION_STAGES.map((s) => ({ id: s.id, label: s.label, desc: s.desc, state: 'pending' as StageState })),
    );
  };

  const patchStage = (id: string, state: StageState, detail?: string) => {
    setPipeline((prev) => {
      if (!prev) return prev;
      return prev.map((s) =>
        s.id === id ? { ...s, state, detail: detail ?? s.detail } : s,
      );
    });
  };

  const markAllFailed = (message: string) => {
    setPipeline((prev) => {
      if (!prev) return prev;
      const started = prev.some((s) => s.state !== 'pending');
      return prev.map((s) => ({
        ...s,
        state: started && s.state === 'pending' ? 'pending' : 'failed',
        detail: s.state === 'running' ? message : s.detail,
      }));
    });
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || isUploading) return;

    setIsUploading(true);
    setUploadMessage(null);
    resetPipeline();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('policy_id', policyId);
    formData.append('policy_type', policyType);
    formData.append('version', version);
    formData.append('effective_date', effectiveDate);

    try {
      const response = await fetch('/documents/stream', {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });

      if (!response.ok || !response.body) {
        const err = await response.json().catch(() => ({ detail: `Upload failed (HTTP ${response.status}).` }));
        markAllFailed(err.detail || 'Upload failed.');
        setUploadMessage({ type: 'error', text: err.detail || 'Upload failed.', });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let result: any = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const rawData = line.slice(6).trim();
          if (rawData === '[DONE]') break;
          let ev: any;
          try {
            ev = JSON.parse(rawData);
          } catch {
            continue;
          }
          if (ev.step) {
            const state: StageState =
              ev.status === 'completed' ? 'passed' : ev.status === 'failed' ? 'failed' : 'running';
            patchStage(ev.step, state, ev.detail);
          }
          if (ev.done) {
            result = ev.result ?? {};
            if (ev.error) {
              markAllFailed(ev.error);
            }
          }
        }
      }

      if (result) {
        if (result.status === 'already_ingested') {
          setPipeline(null);
          setUploadMessage({ type: 'error', text: 'Document already ingested previously.' });
        } else if (result.status === 'success') {
          setUploadMessage({
            type: 'success',
            text: `Document '${file.name}' ingested (${result.inserted_count} chunk${result.inserted_count === 1 ? '' : 's'} stored).`,
          });
          setCorrelationId(result.correlation_id ?? null);
        } else {
          markAllFailed(result.error || 'Ingestion failed.');
          setUploadMessage({ type: 'error', text: result.error || 'Ingestion failed.' });
        }
      }
      setFile(null);
      fetchDocuments();
    } catch {
      // Offline / backend-unreachable fallback: simulate the pipeline stages.
      setUploadMessage({ type: 'success', text: `Document '${file.name}' validated and ingested (simulated).` });
      INGESTION_STAGES.forEach((stage, i) => {
        setTimeout(() => {
          patchStage(stage.id, 'passed', `Simulated ${stage.label.toLowerCase()}`);
        }, 200 * (i + 1));
      });
      setDocuments((prev) => [
        {
          id: 'doc-' + Date.now(),
          filename: file.name,
          policy_id: policyId,
          status: 'ingested',
          created_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      setFile(null);
    } finally {
      setIsUploading(false);
    }
  };

  // Poll run trace events when correlationId is available
  useEffect(() => {
    if (!correlationId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`/runs/${correlationId}`);
        if (res.ok) {
          const events = await res.json();
          if (!cancelled) setTraceEvents(events);
        }
      } catch {
        // ignore polling errors
      }
    };

    const interval = setInterval(poll, 1000);
    poll();
    return () => {
      cancelled = true;
      clearInterval(interval);
      setCorrelationId(null);
    };
  }, [correlationId]);

  return (
    <div className="animate-rise space-y-6">
      <div>
        <span className="eyebrow">
          {canManagePolicies ? 'Document Corpus Pipeline' : 'Policy Library'}
        </span>
        <h2 className="mt-1 page-title">
          {canManagePolicies ? 'Policy Document Ingestion' : 'Available Policies'}
        </h2>
        <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
          {canManagePolicies
            ? 'Upload policy contracts (.pdf, .docx, .txt) with magic-byte signature validation and vector indexing.'
            : 'Browse the ingested policy corpus. Upload and delete are limited to insurer staff.'}
        </p>
      </div>

      {/* Upload Form (corp only) */}
      {canManagePolicies && (
      <form onSubmit={handleUpload} className="soft-card p-5 space-y-4">
        {/* Dropzone */}
        <div className="relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-6 text-center hover:border-[var(--color-accent)] transition-all">
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={handleFileChange}
            className="absolute inset-0 cursor-pointer opacity-0"
          />
          <Upload className="h-8 w-8 text-[var(--color-fg-tertiary)] mb-2" />
          <p className="text-sm font-medium text-[var(--color-fg)]">
            {file ? file.name : 'Click or drop policy document file here'}
          </p>
          <p className="text-xs text-[var(--color-fg-tertiary)] mt-1">
            Supports .pdf (%PDF-), .docx (PK\x03\x04), and .txt formats up to 10MB
          </p>
        </div>

        {/* Metadata Inputs */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Policy ID
            </label>
            <input
              type="text"
              className="karen-input font-mono text-xs"
              value={policyId}
              onChange={(e) => setPolicyId(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Policy Type
            </label>
            <input
              type="text"
              className="karen-input text-xs"
              value={policyType}
              onChange={(e) => setPolicyType(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Version
            </label>
            <input
              type="text"
              className="karen-input font-mono text-xs"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Effective Date
            </label>
            <input
              type="date"
              className="karen-input font-mono text-xs"
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
              required
            />
          </div>
        </div>

        {uploadMessage && (
          <div
            className={`flex items-center gap-2 rounded-xl p-3 text-xs font-medium ${
              uploadMessage.type === 'success'
                ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                : 'bg-red-500/10 text-red-400 border border-red-500/30'
            }`}
          >
            {uploadMessage.type === 'success' ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            {uploadMessage.text}
          </div>
        )}

        {/* Submit */}
        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="submit"
            disabled={!file || isUploading}
            className="btn btn-primary"
          >
            {isUploading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" /> Ingesting Chunks...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" /> Upload & Ingest Policy
              </>
            )}
          </button>
        </div>
      </form>
      )}

      {/* Ingestion Pipeline (Jenkins-style green checks) */}
      {canManagePolicies && pipeline && (
        <div className="soft-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <span className="eyebrow">Ingestion Pipeline</span>
            {isUploading ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--color-fg-secondary)]">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Ingesting…
              </span>
            ) : (
              <span className="text-xs text-[var(--color-fg-tertiary)]">
                {pipeline.some((s) => s.state === 'failed')
                  ? 'Failed'
                  : pipeline.every((s) => s.state === 'passed')
                    ? 'All stages passed'
                    : 'In progress'}
              </span>
            )}
          </div>

          <ol className="space-y-0">
            {pipeline.map((stage, i) => {
              const isLast = i === pipeline.length - 1;
              return (
                <li key={stage.id} className="relative flex gap-3 pb-0">
                  {/* Connector line */}
                  {!isLast && (
                    <span
                      className={`absolute left-[15px] top-8 bottom-0 w-px ${
                        stage.state === 'passed'
                          ? 'bg-emerald-500/40'
                          : 'bg-[var(--color-border)]'
                      }`}
                    />
                  )}

                  {/* Stage icon */}
                  <div className="z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-[var(--color-bg-secondary)]"
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
                    {stage.state === 'passed' && (
                      <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400" />
                    )}
                    {stage.state === 'failed' && (
                      <XCircle className="h-4.5 w-4.5 text-red-400" />
                    )}
                    {stage.state === 'running' && (
                      <RefreshCw className="h-4 w-4 animate-spin text-[var(--color-accent)]" />
                    )}
                    {stage.state === 'pending' && (
                      <Circle className="h-3.5 w-3.5 text-[var(--color-fg-tertiary)]" />
                    )}
                  </div>

                  {/* Stage text */}
                  <div className={`pb-4 pt-1 ${isLast ? '' : ''}`}>
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
                      <p className="mt-1 font-mono text-[11px] text-[var(--color-fg-tertiary)]">
                        {stage.detail}
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}

      {/* Ingested Documents List */}
      <div className="soft-card overflow-hidden">
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <span className="eyebrow">Corpus Index</span>
          <span className="text-xs text-[var(--color-fg-tertiary)]">{documents.length} Active Documents</span>
        </div>
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--color-recessed)] text-xs font-medium text-[var(--color-fg-secondary)] border-b border-[var(--color-border)]">
              <tr>
                <th className="p-3.5">Policy ID</th>
                <th className="p-3.5">Filename</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">Document ID</th>
                <th className="p-3.5 text-right">Ingested At</th>
                {canManagePolicies && <th className="p-3.5 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-[var(--color-bg-tertiary)]">
                  <td className="p-3.5 font-mono text-xs font-semibold text-[var(--color-fg)]">
                    {doc.policy_id ?? '—'}
                  </td>
                  <td className="p-3.5 font-medium text-[var(--color-fg)] flex items-center gap-2">
                    <FileText className="h-4 w-4 text-[var(--color-fg-secondary)]" />
                    {doc.filename}
                  </td>
                  <td className="p-3.5">
                    <span className="inline-flex items-center gap-1 rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-0.5 text-[11px] font-medium text-green-400">
                      <CheckCircle2 className="h-3 w-3" />
                      {doc.status.toUpperCase()}
                    </span>
                  </td>
                  <td className="p-3.5 font-mono text-xs text-[var(--color-fg-tertiary)]">
                    {doc.id}
                  </td>
                  <td className="p-3.5 font-mono text-xs text-right text-[var(--color-fg-secondary)]">
                    {new Date(doc.created_at).toLocaleString()}
                  </td>
                  {canManagePolicies && (
                    <td className="p-3.5 text-right">
                      <button
                        type="button"
                        onClick={() => handleDelete(doc)}
                        disabled={deletingId === doc.id}
                        title={`Remove policy ${doc.policy_id ?? doc.id} from the knowledge base`}
                        className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] px-2 py-1 text-[11px] font-medium text-[var(--color-fg-secondary)] transition-colors hover:border-red-500/40 hover:bg-red-500/10 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {deletingId === doc.id ? (
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ingestion Trace Events (corp only — requires /runs) */}
      {canManagePolicies && traceEvents.length > 0 && (
        <div className="soft-card p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="eyebrow">Ingestion Progress</span>
            <span className="text-xs text-[var(--color-fg-tertiary)]">Live trace</span>
          </div>
          <div className="space-y-2 text-sm font-mono text-[var(--color-fg-secondary)] max-h-48 overflow-auto">
            {traceEvents.map((ev, i) => (
              <div key={i} className="rounded border p-2 bg-[var(--color-panel-elevated)]">
                <div className="text-xs font-medium">{ev.step_name} — {ev.event_type}</div>
                <div className="text-[12px] text-[var(--color-fg)]">{JSON.stringify(ev.payload)}</div>
                <div className="text-[11px] text-[var(--color-fg-tertiary)]">{new Date(ev.timestamp).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
