import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import type { TabType } from './Navbar';
import { useVisibleNavSections } from './nav';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => {
  const sections = useVisibleNavSections();

  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)] lg:flex">
      <nav className="scroll-thin flex-1 space-y-6 overflow-y-auto px-3 py-5">
        {sections.map((section) => (
          <div key={section.label}>
            <div className="tiny-label px-3 pb-2">{section.label}</div>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={`nav-item ${isActive ? 'nav-item-active' : ''}`}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <Icon className="h-4 w-4 shrink-0" strokeWidth={1.9} />
                    <span className="truncate">{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-[var(--color-border)] p-3">
        <div className="rounded-[14px] border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] p-3.5">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-[var(--color-fg)]">
            <CheckCircle2 className="h-3.5 w-3.5 text-[var(--color-success)]" />
            All systems operational
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--color-fg-tertiary)]">
            Retrieval, adjudication workers and approvals are online.
          </p>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
