import React, { useEffect, useState } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import type { TabType } from './components/Navbar';

import { Landing } from './components/Landing';
import { Login } from './components/Login';
import { Register } from './components/Register';
import { Dashboard } from './components/Dashboard';
import { AskQAStream } from './components/AskQAStream';
import { ClaimAdjudication } from './components/ClaimAdjudication';
import { ApprovalsQueue } from './components/ApprovalsQueue';
import { DocumentIngestion } from './components/DocumentIngestion';
import { TraceAuditExplorer } from './components/TraceAuditExplorer';

type View = 'landing' | 'login' | 'register' | 'app';

const canAccessTab = (tab: TabType, role?: string): boolean => {
  switch (tab) {
    case 'qa':
    case 'documents':
      return true; // public
    case 'dashboard':
      return Boolean(role);
    case 'claims':
      return role === 'client';
    case 'approvals':
    case 'trace':
      return role === 'corp';
    default:
      return false;
  }
};

const MainContent: React.FC = () => {
  const { user, loading } = useAuth();
  const [view, setView] = useState<View>('landing');
  const [activeTab, setActiveTab] = useState<TabType>('qa');

  // Redirect to app when a session is restored, otherwise stay on landing.
  useEffect(() => {
    if (!loading && !user) {
      setView('landing');
    }
  }, [loading, user]);

  // Enter the app whenever a user is authenticated (restore, login, or signup).
  useEffect(() => {
    if (user) {
      setView('app');
    }
  }, [user]);

  useEffect(() => {
    if (view !== 'app') return;
    // Reset to an accessible default tab on login/role change.
    if (!canAccessTab(activeTab, user?.role)) {
      setActiveTab(user ? 'dashboard' : 'qa');
    }
  }, [view, user, activeTab]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-backdrop)] text-[var(--color-fg)]">
        <div className="flex items-center gap-2 text-xs text-[var(--color-fg-secondary)]">
          <span className="karen-pulse h-2 w-2 rounded-full bg-[var(--color-accent)]" />
          Restoring session…
        </div>
      </div>
    );
  }

  if (view === 'landing') {
    return (
      <div className="min-h-screen bg-[var(--color-backdrop)] text-[var(--color-fg)] font-sans">
        {/* Transparent nav for the landing page */}
        <header className="sticky top-0 z-50 px-4 py-3 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-border-light)] bg-[var(--color-bg-secondary)] font-mono text-sm font-bold text-[var(--color-fg)]">
                DC
              </div>
              <div className="text-left">
                <div className="eyebrow">Domain Copilot</div>
                <h1 className="text-sm font-semibold tracking-tight text-[var(--color-fg)]">
                  Claims Intelligence
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setView('login')} className="btn btn-ghost btn-sm">
                Log in
              </button>
              <button onClick={() => setView('register')} className="btn btn-primary btn-sm">
                Register
              </button>
            </div>
          </div>
        </header>
        <Landing
          onLogin={() => setView('login')}
          onRegister={() => setView('register')}
          onExplore={() => setView('app')}
        />
      </div>
    );
  }

  if (view === 'login') {
    return (
      <div className="min-h-screen bg-[var(--color-backdrop)] text-[var(--color-fg)] font-sans">
        <Login onBack={() => setView(user ? 'app' : 'landing')} />
      </div>
    );
  }

  if (view === 'register') {
    return (
      <div className="min-h-screen bg-[var(--color-backdrop)] text-[var(--color-fg)] font-sans">
        <Register onBack={() => setView(user ? 'app' : 'landing')} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-backdrop)] text-[var(--color-fg)] flex flex-col font-sans transition-colors duration-200">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onAuthClick={(authView) => setView(authView)}
        onLogoClick={() => setView('landing')}
      />

      <main className="flex-1 mx-auto w-full max-w-6xl px-4 py-8">
        {activeTab === 'dashboard' && canAccessTab('dashboard', user?.role) && (
          <Dashboard setActiveTab={setActiveTab} />
        )}
        {activeTab === 'qa' && <AskQAStream />}
        {activeTab === 'claims' && canAccessTab('claims', user?.role) && (
          <ClaimAdjudication />
        )}
        {activeTab === 'approvals' && canAccessTab('approvals', user?.role) && (
          <ApprovalsQueue />
        )}
        {activeTab === 'documents' && <DocumentIngestion />}
        {activeTab === 'trace' && canAccessTab('trace', user?.role) && (
          <TraceAuditExplorer />
        )}
      </main>

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
