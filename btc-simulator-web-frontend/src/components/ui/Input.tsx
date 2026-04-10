import React from 'react';
import { clsn } from '../../utils/format';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  leftAddon?: React.ReactNode;
  rightAddon?: React.ReactNode;
}

export function Input({
  label,
  hint,
  error,
  leftAddon,
  rightAddon,
  className,
  ...props
}: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        {leftAddon && (
          <span className="absolute left-3 text-zinc-500 text-sm pointer-events-none">
            {leftAddon}
          </span>
        )}
        <input
          className={clsn(
            'w-full bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-100 placeholder-zinc-600',
            'focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-600 transition-colors',
            'py-2',
            leftAddon ? 'pl-8' : 'pl-3',
            rightAddon ? 'pr-12' : 'pr-3',
            error && 'border-rose-500 focus:ring-rose-500/50',
            className
          )}
          {...props}
        />
        {rightAddon && (
          <span className="absolute right-3 text-zinc-500 text-xs pointer-events-none">
            {rightAddon}
          </span>
        )}
      </div>
      {hint && !error && <p className="text-xs text-zinc-500">{hint}</p>}
      {error && <p className="text-xs text-rose-400">{error}</p>}
    </div>
  );
}

interface SliderProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  valueLabel?: string;
}

export function Slider({ label, valueLabel, className, ...props }: SliderProps) {
  return (
    <div className="flex flex-col gap-1">
      {(label || valueLabel) && (
        <div className="flex items-center justify-between">
          {label && <span className="text-xs font-medium text-zinc-400 uppercase tracking-wide">{label}</span>}
          {valueLabel && <span className="text-xs text-sky-400 font-mono font-semibold">{valueLabel}</span>}
        </div>
      )}
      <input
        type="range"
        className={clsn(
          'w-full h-1.5 bg-zinc-700 rounded-full appearance-none cursor-pointer',
          '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4',
          '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-sky-500',
          '[&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:cursor-pointer',
          className
        )}
        {...props}
      />
    </div>
  );
}
