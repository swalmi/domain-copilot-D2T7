import React from 'react';

interface LogoMarkProps {
  className?: string;
}

export const LogoMark: React.FC<LogoMarkProps> = ({ className = 'h-5 w-5' }) => (
  <svg
    viewBox="0 0 64 64"
    className={className}
    fill="none"
    aria-hidden="true"
    focusable="false"
  >
    <path
      d="M32 10.5l17 6.8v13.8c0 11-7.3 20.7-17 24.2-9.7-3.5-17-13.2-17-24.2V17.3l17-6.8z"
      stroke="currentColor"
      strokeWidth="4"
      strokeLinejoin="round"
    />
    <path
      d="M24.5 31.8l5.4 5.4L40.5 26"
      stroke="currentColor"
      strokeWidth="4.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

interface BrandProps {
  onClick?: () => void;
  compact?: boolean;
  className?: string;
}

export const Brand: React.FC<BrandProps> = ({ onClick, compact, className = '' }) => (
  <button
    type="button"
    onClick={onClick}
    className={`group flex items-center gap-2.5 text-left ${className}`}
    title="insureAI — home"
  >
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[var(--color-accent)] text-[var(--color-accent-contrast)] shadow-[0_2px_8px_rgba(15,23,42,0.16)] transition-transform duration-200 group-hover:-translate-y-px">
      <LogoMark className="h-[18px] w-[18px]" />
    </span>
    {!compact && (
      <span className="flex flex-col leading-none">
        <span className="text-[15px] font-extrabold tracking-[-0.02em] text-[var(--color-fg)]">
          insureAI
        </span>
        <span className="mt-1 text-[9px] font-bold uppercase tracking-[0.16em] text-[var(--color-fg-tertiary)]">
          Claims Intelligence
        </span>
      </span>
    )}
  </button>
);

export default Brand;
