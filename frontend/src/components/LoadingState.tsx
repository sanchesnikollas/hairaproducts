import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

/**
 * Inline loading — substituto pro `<p>Carregando…</p>` adhoc nos painéis Ops.
 *
 * Usa Skeleton dimensionada (não tem layout shift quando data chega),
 * inclui `aria-busy` pra leitor de tela.
 *
 * Variantes:
 * - `pulse` (default): retangulo cinza pulsante, dimensionado por `width`
 * - `dots`: 3 dots animados (mais discreto, bom em headers)
 */
export function InlineLoading({
  width = '8rem',
  variant = 'pulse',
  label = 'Carregando',
}: {
  width?: string;
  variant?: 'pulse' | 'dots';
  label?: string;
}) {
  if (variant === 'dots') {
    return (
      <span
        role="status"
        aria-busy="true"
        aria-label={label}
        className="inline-flex items-center gap-1 text-ink-faint"
      >
        <span className="inline-block w-1 h-1 rounded-full bg-current animate-pulse" style={{ animationDelay: '0ms' }} />
        <span className="inline-block w-1 h-1 rounded-full bg-current animate-pulse" style={{ animationDelay: '200ms' }} />
        <span className="inline-block w-1 h-1 rounded-full bg-current animate-pulse" style={{ animationDelay: '400ms' }} />
      </span>
    );
  }
  return (
    <Skeleton
      role="status"
      aria-busy="true"
      aria-label={label}
      className="inline-block h-4 align-middle rounded"
      style={{ width }}
    />
  );
}

export default function LoadingState({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="space-y-6 py-8">
      <p className="text-sm text-muted-foreground">{message}</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <Card key={i}>
            <CardContent className="space-y-3 pt-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <Card className="max-w-md w-full">
        <CardContent className="flex flex-col items-center gap-4 pt-2 text-center">
          <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-destructive">
              <path d="M12 9v4" strokeLinecap="round" />
              <path d="M12 17h.01" strokeLinecap="round" />
              <circle cx="12" cy="12" r="10" />
            </svg>
          </div>
          <Badge variant="destructive">Error</Badge>
          <p className="text-sm text-muted-foreground">{message}</p>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              Try again
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-3">
      <div className="w-12 h-12 rounded-full bg-muted/50 flex items-center justify-center">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
    </div>
  );
}
