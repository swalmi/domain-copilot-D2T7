import React, { useState } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import type { TabType } from './components/Navbar';

import { AskQAStream } from './components/AskQAStream';
import { ClaimAdjudication } from './components/ClaimAdjudication';
import { ApprovalsQueue } from './components/ApprovalsQueue';
import { DocumentIngestion } from './components/DocumentIngestion';
import { TraceAuditExplorer } from './components/TraceAuditExplorer';

const MainContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('qa');
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[var(--color-backdrop)] text-[var(--color-fg)] flex flex-col font-sans transition-colors duration-200">
      {/* Navigation Bar */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Container */}
      <main className="flex-1 mx-auto w-full max-w-6xl px-4 py-8">
        {/* Active Role Banner */}
        <div className="mb-6 flex items-center justify-between rounded-xl border border-[var(--color-border)] bg-[var(--color-panel)] px-4 py-2.5">
          <div className="flex items-center gap-2 text-xs">
            <span className="eyebrow">Active Session</span>
            <span className="font-mono text-[var(--color-fg-secondary)]">{user?.email}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-[var(--color-fg-tertiary)]">Current Role:</span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider font-mono ${
                user?.role === 'adjuster'
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                  : 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
              }`}
            >
              {user?.role.replace('_', ' ')}
            </span>
          </div>
        </div>

        {/* Tab Views */}
        {activeTab === 'qa' && <AskQAStream />}
        {activeTab === 'claims' && <ClaimAdjudication />}
        {activeTab === 'approvals' && <ApprovalsQueue />}
        {activeTab === 'documents' && <DocumentIngestion />}
        {activeTab === 'trace' && <TraceAuditExplorer />}
      </main>

      {/* Quiet Footer */}
      <footer className="border-t border-[var(--color-border)] py-6 text-center text-xs text-[var(--color-fg-tertiary)]">
        <div className="mx-auto max-w-6xl flex flex-wrap items-center justify-between px-4">
          <span>Domain Copilot • ITI Technical Assessment Variant D2T7</span>
          <span className="font-mono text-[11px]">Dark-First Monochrome UI • React + Vite + Tailwind v4</span>
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <MainContent />
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
