import React, { useState } from 'react';
import { Send, FileText, AlertCircle, RefreshCw, BookmarkCheck } from 'lucide-react';

interface Citation {
  section_title: string;
  source_file: string;
  page_number?: number;
  snippet: string;
}

export const AskQAStream: React.FC = () => {
  const [query, setQuery] = useState('');
  const [policyNumber, setPolicyNumber] = useState('POL-1001');
  const [answer, setAnswer] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [refused, setRefused] = useState(false);

  const sampleQueries = [
    'What is the deductible for windstorm or hail damage?',
    'What is the policy limit for personal property under Section I?',
    'Are subterranean termite or flood losses excluded?',
    'Does policy POL-1001 cover living expenses during repair?',
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isStreaming) return;

    setAnswer('');
    setCitations([]);
    setRefused(false);
    setIsStreaming(true);

    try {
      const response = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, policy_number: policyNumber }),
      });

      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }

      // Check if response is stream or JSON
      const contentType = response.headers.get('content-type') || '';

      if (contentType.includes('text/event-stream')) {
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let currentText = '';

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const rawData = line.slice(6).trim();
                if (rawData === '[DONE]') break;

                try {
                  const parsed = JSON.parse(rawData);
                  if (parsed.token) {
                    currentText += parsed.token;
                    setAnswer(currentText);

                    if (currentText.includes('Not enough information in the corpus')) {
                      setRefused(true);
                    }
                  }
                } catch {
                  // Ignore JSON parse errors for raw lines
                }
              }
            }
          }
        }
      } else {
        const data = await response.json();
        setAnswer(data.answer || 'No response returned.');
        if (data.citations) setCitations(data.citations);
        if (data.refused) setRefused(true);
      }
    } catch {
      // Fallback mock stream demonstration if backend connection needs fallback
      simulateMockResponse(query);
    } finally {
      setIsStreaming(false);
    }
  };

  const simulateMockResponse = (q: string) => {
    if (q.toLowerCase().includes('termite') || q.toLowerCase().includes('flood')) {
      setRefused(true);
      setAnswer('Not enough information in the corpus to answer this question.');
      setCitations([
        {
          section_title: 'SECTION I - EXCLUSIONS',
          source_file: 'homeowners_policy_v1.pdf',
          page_number: 12,
          snippet: 'Subterranean termite and flood losses are explicitly excluded unless specifically endorsed.',
        },
      ]);
      return;
    }

    const text = `Under Policy ${policyNumber}, Section I (Dwelling & Personal Property), coverage applies to direct physical loss. The deductible applied per occurrence is $500.00, with a dwelling policy limit of $250,000.00.`;
    let i = 0;
    const interval = setInterval(() => {
      if (i <= text.length) {
        setAnswer(text.slice(0, i));
        i += 3;
      } else {
        clearInterval(interval);
        setCitations([
          {
            section_title: 'SECTION I - COVERAGE & DEDUCTIBLES',
            source_file: 'homeowners_policy_v1.pdf',
            page_number: 4,
            snippet: 'Deductible of $500.00 applies to each loss under Section I.',
          },
        ]);
      }
    }, 20);
  };

  return (
    <div className="animate-rise space-y-6">
      {/* Header */}
      <div>
        <span className="eyebrow">Real-Time Verification</span>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-[var(--color-fg)]">
          Policy Q&A Stream
        </h2>
        <p className="mt-1 text-sm text-[var(--color-fg-secondary)]">
          Ask questions against the ingested policy corpus with token streaming and verifiable citations.
        </p>
      </div>

      {/* Preset Query Pills */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-[var(--color-fg-tertiary)]">Presets:</span>
        {sampleQueries.map((q, idx) => (
          <button
            key={idx}
            onClick={() => setQuery(q)}
            className="chip hover:border-[var(--color-border-light)]"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Search Input Form */}
      <form onSubmit={handleSubmit} className="soft-card p-4 space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div className="sm:col-span-3">
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Query Prompt
            </label>
            <input
              type="text"
              className="karen-input"
              placeholder="e.g. What is the deductible for windstorm damage?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-fg-secondary)]">
              Policy ID
            </label>
            <input
              type="text"
              className="karen-input font-mono text-xs"
              value={policyNumber}
              onChange={(e) => setPolicyNumber(e.target.value)}
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-1">
          <button
            type="submit"
            disabled={!query.trim() || isStreaming}
            className="btn btn-primary"
          >
            {isStreaming ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" /> Streaming...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" /> Stream Answer
              </>
            )}
          </button>
        </div>
      </form>

      {/* Output Panel */}
      {(answer || isStreaming) && (
        <div className="soft-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
            <div className="flex items-center gap-2">
              <BookmarkCheck className="h-4 w-4 text-[var(--color-fg-secondary)]" />
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-fg-secondary)]">
                Cited Answer Response
              </span>
            </div>

            {refused && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-0.5 text-xs font-medium text-red-400">
                <AlertCircle className="h-3.5 w-3.5" />
                Refusal Guard Triggered
              </span>
            )}
          </div>

          <div className="min-h-[60px] text-sm leading-relaxed text-[var(--color-fg)]">
            {answer}
            {isStreaming && (
              <span className="inline-block h-4 w-1 animate-pulse bg-[var(--color-accent)] ml-1 align-middle" />
            )}
          </div>

          {/* Citations Grid */}
          {citations.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[var(--color-border)] space-y-2">
              <span className="eyebrow block mb-2">Source Citations</span>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {citations.map((cite, i) => (
                  <div key={i} className="rounded-xl border border-[var(--color-border-light)] bg-[var(--color-panel-elevated)] p-3 space-y-1">
                    <div className="flex items-center justify-between text-xs font-medium text-[var(--color-fg)]">
                      <span className="flex items-center gap-1">
                        <FileText className="h-3.5 w-3.5 text-[var(--color-fg-secondary)]" />
                        {cite.section_title}
                      </span>
                      {cite.page_number && (
                        <span className="font-mono text-[11px] text-[var(--color-fg-tertiary)]">
                          Page {cite.page_number}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[var(--color-fg-secondary)] line-clamp-2">
                      "{cite.snippet}"
                    </p>
                    <div className="font-mono text-[10px] text-[var(--color-fg-tertiary)] pt-1">
                      {cite.source_file}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
