import React from 'react';
import {
  FileText,
  MessageSquare,
  ShieldCheck,
  Zap,
  Activity,
  Moon,
  Sun,
  LogOut,
  LayoutDashboard,
  ScrollText,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';

export type TabType =
  | 'dashboard'
  | 'qa'
  | 'claims'
  | 'approvals'
  | 'documents'
  | 'trace';

interface NavbarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  onAuthClick: (view: 'login' | 'register') => void;
  onLogoClick: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  onAuthClick,
  onLogoClick,
}) => {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  const navItems: { id: TabType; label: string; icon: typeof MessageSquare; public: boolean; roles?: ('client' | 'corp')[] }[] = [
    { id: 'qa' as TabType, label: 'Ask', icon: MessageSquare, public: true },
    { id: 'documents' as TabType, label: 'Policies', icon: FileText, public: true },
    { id: 'dashboard' as TabType, label: 'Dashboard', icon: LayoutDashboard, public: false },
    { id: 'claims' as TabType, label: 'Claim Adjudication', icon: Zap, public: false, roles: ['client'] },
    { id: 'approvals' as TabType, label: 'Approvals', icon: ShieldCheck, public: false, roles: ['corp'] },
    { id: 'trace' as TabType, label: 'Audit Trace', icon: Activity, public: false, roles: ['corp'] },
  ];

  const visible = navItems.filter((item) => {
    if (item.public) return true;
    if (!user) return false;
    if (item.roles) return item.roles.includes(user.role);
    return true;
  });

  return (
    <header className="sticky top-0 z-50 border-b border-transparent bg-transparent px-4 py-3 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        {/* Brand */}
        <button
          onClick={onLogoClick}
          className="flex items-center gap-3"
          title="Back to home"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-border-light)] bg-[var(--color-bg-secondary)] font-mono text-sm font-bold text-[var(--color-fg)]">
            DC
          </div>
          <div className="text-left">
            <div className="eyebrow">Domain Copilot</div>
            <h1 className="text-sm font-semibold tracking-tight text-[var(--color-fg)]">
              Claims Intelligence
            </h1>
          </div>
        </button>

        {/* Navigation Tabs (public + role-gated) */}
        <nav className="hidden items-center gap-1.5 md:flex">
          {visible.map((item) => {
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

        {/* Auth + Theme Controls */}
        <div className="flex items-center gap-2.5">
          {user ? (
            <div className="flex items-center gap-2">
              <div className="hidden items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-1.5 sm:flex">
                <ScrollText className="h-3.5 w-3.5 text-[var(--color-fg-secondary)]" />
                <span className="max-w-[160px] truncate text-[11px] font-medium text-[var(--color-fg-secondary)]">
                  {user.email}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                    user.role === 'corp'
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                      : 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                  }`}
                >
                  {user.role}
                </span>
              </div>
              <button
                onClick={() => logout()}
                className="flex h-8 items-center gap-1.5 rounded-full border border-[var(--color-border-light)] bg-[var(--color-bg-secondary)] px-3 text-xs font-medium text-[var(--color-fg-secondary)] transition-all hover:text-[var(--color-fg)]"
                title="Log out"
              >
                <LogOut className="h-3.5 w-3.5" /> Logout
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onAuthClick('login')}
                className="btn btn-ghost btn-sm"
              >
                Log in
              </button>
              <button
                onClick={() => onAuthClick('register')}
                className="btn btn-primary btn-sm"
              >
                Register
              </button>
            </div>
          )}

          {/* Theme Toggle */}
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
