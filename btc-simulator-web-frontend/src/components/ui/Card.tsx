import React from 'react';
import { clsn } from '../../utils/format';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  titleRight?: React.ReactNode;
  noPad?: boolean;
}

export function Card({ children, className, title, titleRight, noPad }: CardProps) {
  return (
    <div
      className={clsn(
        'bg-zinc-900 border border-zinc-800 rounded-xl',
        !noPad && !title && 'p-4',
        className
      )}
    >
      {title && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <span className="text-sm font-semibold text-zinc-300 tracking-wide uppercase">{title}</span>
          {titleRight && <div>{titleRight}</div>}
        </div>
      )}
      {title ? <div className={clsn(!noPad && 'p-4')}>{children}</div> : children}
    </div>
  );
}
