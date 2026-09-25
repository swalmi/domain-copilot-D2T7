import React from 'react';
import { Moon, Sun, LogOut } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { Brand } from './Brand';
import { useVisibleNavSections } from './nav';

export type TabType =
  | 'dashboard'
  | 'profile'
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

const initials = (email: string): string =>
  email
    .split('@')[0]
    .split(/[._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('') || '?';

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  onAuthClick,
  onLogoClick,
}) => {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const sections = useVisibleNavSections();
  const flatItems = sections.flatMap((section) => section.items);

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-border)] bg-[var(--color-bg)]/90 backdrop-blur-md">
      <div className="page-shell flex h-16 items-center justify-between gap-4 px-4 md:px-6">
        <Brand onClick={onLogoClick} />

        <div className="flex items-center gap-2">
          {user ? (
            <>
              <div className="hidden items-center gap-2.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-secondary)] py-1 pl-1 pr-3 sm:flex">
                <span className="avatar h-7 w-7 text-[11px]">{initials(user.email)}</span>
                <span className="max-w-[150px] truncate text-xs font-medium text-[var(--color-fg-secondary)]">
                  {user.email}
                </span>
                <span
                  className={`badge ${
                    user.role === 'corp' ? 'badge-warning' : 'badge-neutral'
                  }`}
                >
                  {user.role}
                </span>
              </div>
              <button
                onClick={() => logout()}
                className="btn btn-ghost btn-sm"
                title="Log out"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </>
          ) : (
            <>
              <button onClick={() => onAuthClick('login')} className="btn btn-ghost btn-sm">
                Log in
              </button>
              <button onClick={() => onAuthClick('register')} className="btn btn-primary btn-sm">
                Get started
              </button>
            </>
          )}

          <button
            onClick={toggleTheme}
            className="btn btn-ghost btn-icon"
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            aria-label="Toggle color theme"
          >
            {theme === 'dark' ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile navigation — replaces the desktop sidebar */}
      <div className="scroll-thin border-t border-[var(--color-border)] lg:hidden">
        <div className="page-shell flex items-center gap-1.5 overflow-x-auto px-4 py-2 md:px-6">
          {flatItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex shrink-0 items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-xs font-semibold transition-colors ${
                  isActive
                    ? 'bg-[var(--color-accent)] text-[var(--color-accent-contrast)]'
                    : 'border border-[var(--color-border)] bg-[var(--color-bg-secondary)] text-[var(--color-fg-secondary)] hover:text-[var(--color-fg)]'
                }`}
              >
                <Icon className="h-3.5 w-3.5" strokeWidth={1.9} />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};

export default Navbar;
