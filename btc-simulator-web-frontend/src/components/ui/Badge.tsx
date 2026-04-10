import React from 'react';
import { clsn } from '../../utils/format';

type Variant = 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'purple';

const variants: Record<Variant, string> = {
  green: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  red: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  yellow: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  blue: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  gray: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  purple: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
};

interface BadgeProps {
  variant?: Variant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'gray', children, className }: BadgeProps) {
  return (
    <span
      className={clsn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
