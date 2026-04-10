import React from 'react';
import { clsn } from '../../utils/format';

type Variant = 'primary' | 'ghost' | 'danger' | 'success' | 'warning' | 'outline';
type Size = 'xs' | 'sm' | 'md' | 'lg';

const variantCls: Record<Variant, string> = {
  primary:
    'bg-sky-600 hover:bg-sky-500 text-white border border-sky-600 hover:border-sky-500',
  ghost:
    'bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 hover:border-zinc-600',
  danger:
    'bg-rose-600/80 hover:bg-rose-600 text-white border border-rose-600',
  success:
    'bg-emerald-600/80 hover:bg-emerald-600 text-white border border-emerald-600',
  warning:
    'bg-amber-600/80 hover:bg-amber-600 text-white border border-amber-600',
  outline:
    'bg-transparent hover:bg-zinc-800 text-zinc-300 border border-zinc-700',
};

const sizeCls: Record<Size, string> = {
  xs: 'px-2 py-1 text-xs rounded',
  sm: 'px-3 py-1.5 text-xs rounded-md',
  md: 'px-4 py-2 text-sm rounded-md',
  lg: 'px-5 py-2.5 text-sm rounded-lg',
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export function Button({
  variant = 'ghost',
  size = 'md',
  isLoading,
  leftIcon,
  rightIcon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsn(
        'inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-sky-500/50 cursor-pointer',
        variantCls[variant],
        sizeCls[size],
        (disabled || isLoading) && 'opacity-50 cursor-not-allowed pointer-events-none',
        className
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
      ) : leftIcon ? (
        <span className="flex-shrink-0">{leftIcon}</span>
      ) : null}
      {children}
      {rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
    </button>
  );
}
