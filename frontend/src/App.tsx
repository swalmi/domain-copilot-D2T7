import React, { useEffect, useRef, useState } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import type { TabType } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { Brand, LogoMark } from './components/Brand';

import { Landing } from './components/Landing';
import { Login } from './components/Login';
import { Register } from './components/Register';
import { Dashboard } from './components/Dashboard';
import { Profile } from './components/Profile';
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
      return role === 'corp';
    case 'profile':
      return role === 'client';
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

  // Land on the role's home tab the first time a session becomes available
  // (login, signup, or session restore) instead of the public Q&A tab.
  const lastUserRef = useRef<string | null>(null);
  useEffect(() => {
    const id = user?.id ?? null;
    if (id && id !== lastUserRef.current) {
      setActiveTab(user!.role === 'corp' ? 'dashboard' : 'claims');
    }
    lastUserRef.current = id;
  }, [user]);

  useEffect(() => {
    if (view !== 'app') return;
    // Reset to an accessible default tab on login/role change.
    if (!canAccessTab(activeTab, user?.role)) {
      setActiveTab(user ? (user.role === 'corp' ? 'dashboard' : 'claims') : 'qa');
    }
  }, [view, user, activeTab]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)] text-[var(--color-fg)]">
        <div className="flex items-center gap-2.5 text-xs font-medium text-[var(--color-fg-secondary)]">
          <span className="pulse-dot h-2 w-2 rounded-full bg-[var(--color-accent)]" />
          Restoring session…
        </div>
      </div>
    );
  }

  if (view === 'landing') {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-fg)] font-sans">
        <header className="sticky top-0 z-30 border-b border-transparent backdrop-blur-md">
          <div className="page-shell flex h-16 items-center justify-between px-4 md:px-6">
            <Brand onClick={() => setView('landing')} />
            <div className="flex items-center gap-2">
              <button onClick={() => setView('login')} className="btn btn-ghost btn-sm">
                Log in
              </button>
              <button onClick={() => setView('register')} className="btn btn-primary btn-sm">
                Get started
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
    <div className="flex min-h-screen flex-col bg-[var(--color-bg)] font-sans text-[var(--color-fg)] transition-colors duration-200">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onAuthClick={(authView) => setView(authView)}
        onLogoClick={() => setView('landing')}
      />

      <div className="page-shell flex flex-1 items-stretch">
        <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

        <main className="min-w-0 flex-1 px-4 py-6 md:px-6 lg:px-8 lg:py-8">
          {activeTab === 'dashboard' && canAccessTab('dashboard', user?.role) && (
            <Dashboard setActiveTab={setActiveTab} />
          )}
          {activeTab === 'profile' && canAccessTab('profile', user?.role) && <Profile />}
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
      </div>

      <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="page-shell flex flex-wrap items-center justify-between gap-3 px-4 py-5 md:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--color-accent)] text-[var(--color-accent-contrast)]">
              <LogoMark className="h-3.5 w-3.5" />
            </span>
            <span className="text-xs font-semibold text-[var(--color-fg-secondary)]">
              insureAI — agentic claims intelligence
            </span>
          </div>
          <span className="font-mono text-[11px] text-[var(--color-fg-tertiary)]">
            React + TypeScript + Tailwind · Light &amp; dark themes
          </span>
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
