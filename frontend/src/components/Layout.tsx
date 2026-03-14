import { useEffect, useState, useCallback } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { getQuarantine } from '@/lib/api';
import GlobalSearch from '@/components/GlobalSearch';

const navItems = [
  { to: '/', label: 'Dashboard', icon: dashboardIcon },
  { to: '/brands', label: 'Brands', icon: brandsIcon },
  { to: '/products', label: 'Products', icon: productIcon },
  { to: '/quarantine', label: 'Quarantine', icon: quarantineIcon },
  { to: '/review-queue', label: 'Review Queue', icon: reviewQueueIcon },
];

function dashboardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12h4l3-9 4 18 3-9h4" />
    </svg>
  );
}

function brandsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4-4v-2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 00-3-3.87" />
      <path d="M16 3.13a4 4 0 010 7.75" />
    </svg>
  );
}

function productIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2h6l3 7H6L9 2z" />
      <rect x="4" y="9" width="16" height="13" rx="2" />
      <path d="M10 13h4" />
    </svg>
  );
}

function quarantineIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    </svg>
  );
}

function reviewQueueIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
    </svg>
  );
}

export default function Layout() {
  const [quarantineCount, setQuarantineCount] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);

  const fetchQuarantineCount = useCallback(async () => {
    try {
      const items = await getQuarantine('pending');
      setQuarantineCount(items.length);
    } catch {
      // Silently fail — badge just won't show
    }
  }, []);

  useEffect(() => {
    // Initial fetch + polling
    const controller = new AbortController();
    getQuarantine('pending')
      .then((items) => {
        if (!controller.signal.aborted) setQuarantineCount(items.length);
      })
      .catch(() => {});
    const interval = setInterval(fetchQuarantineCount, 60_000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [fetchQuarantineCount]);

  // Cmd+K / Ctrl+K keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="grain-overlay min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-ink/5 bg-white/60 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-8 flex items-center justify-between h-16">
          <motion.div
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-3"
          >
            <span className="font-display text-2xl font-semibold tracking-tight text-ink">
              HAIRA
            </span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-ink-muted font-medium mt-1">
              Intelligence
            </span>
          </motion.div>

          <nav className="flex items-center gap-0">
            {navItems.map((item, i) => (
              <motion.div
                key={item.to}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.1 + i * 0.05 }}
              >
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'relative flex items-center gap-2 px-4 py-2 text-sm transition-colors duration-200',
                      isActive
                        ? 'text-champagne-dark font-medium'
                        : 'text-ink-muted hover:text-ink'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon />
                      <span>{item.label}</span>
                      {item.to === '/quarantine' && quarantineCount > 0 && (
                        <Badge variant="destructive" className="ml-1 h-4 px-1.5 text-[10px] leading-none">
                          {quarantineCount}
                        </Badge>
                      )}
                      {isActive && (
                        <motion.div
                          layoutId="nav-underline"
                          className="absolute bottom-0 left-2 right-2 h-0.5 bg-champagne rounded-full"
                          transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                        />
                      )}
                    </>
                  )}
                </NavLink>
              </motion.div>
            ))}
          </nav>

          {/* Cmd+K Search Trigger */}
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-ink/10 bg-ink/[0.02] px-3 py-1.5 text-xs text-ink-muted hover:text-ink hover:border-ink/20 transition-colors duration-200"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
            <span className="hidden sm:inline">Search</span>
            <kbd className="pointer-events-none hidden sm:inline-flex h-5 items-center gap-0.5 rounded border border-ink/10 bg-ink/[0.04] px-1.5 font-mono text-[10px] font-medium text-ink-faint">
              <span className="text-xs">⌘</span>K
            </kbd>
          </motion.button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-[1400px] mx-auto w-full px-8 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-ink/5 py-6">
        <div className="max-w-[1400px] mx-auto px-8 flex items-center justify-between text-xs text-ink-faint">
          <span>HAIRA v2 &mdash; Hair Product Intelligence Platform</span>
          <span className="font-display italic">Evidence-based beauty data</span>
        </div>
      </footer>

      {/* Global Search */}
      <GlobalSearch open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  );
}
