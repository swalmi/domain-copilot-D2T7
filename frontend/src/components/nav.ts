import {
  FileText,
  MessageSquare,
  ShieldCheck,
  Zap,
  Activity,
  LayoutDashboard,
  User,
} from 'lucide-react';
import type { TabType } from './Navbar';
import { useAuth } from '../context/AuthContext';

export interface NavItem {
  id: TabType;
  label: string;
  icon: typeof MessageSquare;
  roles?: ('client' | 'corp')[];
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    label: 'Workspace',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['corp'] },
      { id: 'profile', label: 'Profile', icon: User, roles: ['client'] },
      { id: 'qa', label: 'Ask insureAI', icon: MessageSquare },
      { id: 'documents', label: 'Policy Library', icon: FileText },
    ],
  },
  {
    label: 'Claims',
    items: [
      { id: 'claims', label: 'Claim Adjudication', icon: Zap, roles: ['client'] },
      { id: 'approvals', label: 'Approvals Queue', icon: ShieldCheck, roles: ['corp'] },
    ],
  },
  {
    label: 'Oversight',
    items: [{ id: 'trace', label: 'Audit Trace', icon: Activity, roles: ['corp'] }],
  },
];

export const useVisibleNavSections = (): NavSection[] => {
  const { user } = useAuth();
  return navSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        if (!item.roles) return true;
        if (!user) return false;
        return item.roles.includes(user.role);
      }),
    }))
    .filter((section) => section.items.length > 0);
};
