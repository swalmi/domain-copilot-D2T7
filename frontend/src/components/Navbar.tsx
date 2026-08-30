import React from 'react';
import {
  FileText,
  MessageSquare,
  ShieldCheck,
  Zap,
  Activity,
  Moon,
  Sun,
  UserCheck,
  ShieldAlert,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../context/AuthContext';


export type TabType = 'qa' | 'claims' | 'approvals' | 'documents' | 'trace';

interface NavbarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const { theme, toggleTheme } = useTheme();
  const { user, setRole } = useAuth();

  const navItems = [
    { id: 'qa' as TabType, label: 'Q&A Stream', icon: MessageSquare },
    { id: 'claims' as TabType, label: 'Claim Adjudication', icon: Zap },
    { id: 'approvals' as TabType, label: 'Approvals Queue', icon: ShieldCheck },
    { id: 'documents' as TabType, label: 'Policy Documents', icon: FileText },
    { id: 'trace' as TabType, label: 'Trace Audit', icon: Activity },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-panel)] px-4 py-3 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-border-light)] bg-[var(--color-bg-secondary)] font-mono text-sm font-bold text-[var(--color-fg)]">
            D2
          </div>
          <div>
            <div className="eyebrow">Variant D2T7</div>
            <h1 className="text-sm font-semibold tracking-tight text-[var(--color-fg)]">
              Domain Copilot
            </h1>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden items-center gap-1.5 md:flex">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-[var(--color-active-bg)] text-[var(--color-active-fg)] border border-[var(--color-border-light)]'
                    : 'text-[var(--color-fg-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-fg)]'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Status, Role & Theme Controls */}
        <div className="flex items-center gap-2.5">
          {/* Live Readiness Pulse */}
          <span className="hidden items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-2.5 py-1 text-[11px] font-medium text-[var(--color-fg-secondary)] sm:flex">
            <span className="karen-pulse h-1.5 w-1.5 rounded-full bg-[var(--color-success)]" aria-hidden="true" />
            Backend Ready
          </span>

          {/* Role Switcher */}
          <div className="flex items-center rounded-full border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-0.5">
            <button
              onClick={() => setRole('claims_handler')}
              className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all ${
                user?.role === 'claims_handler'
                  ? 'bg-[var(--color-accent)] text-[var(--color-accent-contrast)]'
                  : 'text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)]'
              }`}
              title="Switch to Claims Handler Role"
            >
              <UserCheck className="h-3 w-3" />
              Handler
            </button>
            <button
              onClick={() => setRole('adjuster')}
              className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all ${
                user?.role === 'adjuster'
                  ? 'bg-[var(--color-accent)] text-[var(--color-accent-contrast)]'
                  : 'text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)]'
              }`}
              title="Switch to Senior Adjuster Role"
            >
              <ShieldAlert className="h-3 w-3" />
              Adjuster
            </button>
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border-light)] bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] transition-all hover:text-[var(--color-fg)]"
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          >
            {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>
    </header>
  );
};
