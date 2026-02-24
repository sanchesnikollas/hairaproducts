import { motion } from 'motion/react';

export default function LoadingState({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <motion.div
        className="w-8 h-8 rounded-full border-2 border-champagne-light border-t-champagne"
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      />
      <span className="text-sm text-ink-muted">{message}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <div className="w-12 h-12 rounded-full bg-coral-bg flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-coral">
          <path d="M12 9v4" strokeLinecap="round" />
          <path d="M12 17h.01" strokeLinecap="round" />
          <circle cx="12" cy="12" r="10" />
        </svg>
      </div>
      <p className="text-sm text-ink-muted text-center max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium text-champagne-dark hover:text-champagne transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-3">
      <div className="w-12 h-12 rounded-full bg-ink/3 flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-ink-faint">
          <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-sm font-medium text-ink-light">{title}</p>
      {description && <p className="text-xs text-ink-muted">{description}</p>}
    </div>
  );
}
