import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';
import GlobalSearch from '@/components/GlobalSearch';

const navItems = [
  { to: '/', label: 'Home', icon: homeIcon },
  { to: '/brands', label: 'Brands', icon: brandsIcon },
  { to: '/explorer', label: 'Explorador', icon: productIcon },
  { to: '/ops', label: 'Ops', icon: opsIcon },
];

function homeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
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

function opsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export default function Layout() {
  const [searchOpen, setSearchOpen] = useState(false);

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
      <header className="border-b border-neutral-200/60 bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-8 flex items-center justify-between h-14">
          <motion.div
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-3"
          >
            <span className="text-lg font-semibold tracking-tight text-neutral-900">
              HAIRA
            </span>
            <span className="text-[10px] uppercase tracking-[0.15em] text-neutral-400 font-medium mt-0.5">
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
                      'relative flex items-center gap-2 px-3.5 py-2 text-sm transition-colors duration-200',
                      isActive
                        ? 'text-neutral-900 font-medium'
                        : 'text-neutral-400 hover:text-neutral-700'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon />
                      <span>{item.label}</span>
                      {isActive && (
                        <motion.div
                          layoutId="nav-underline"
                          className="absolute bottom-0 left-2 right-2 h-0.5 bg-neutral-900 rounded-full"
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
            className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 transition-colors duration-200"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
            <span className="hidden sm:inline">Search</span>
            <kbd className="pointer-events-none hidden sm:inline-flex h-5 items-center gap-0.5 rounded border border-neutral-200 bg-neutral-50 px-1.5 font-mono text-[10px] font-medium text-neutral-400">
              <span className="text-xs">&#x2318;</span>K
            </kbd>
          </motion.button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-[1400px] mx-auto w-full px-8 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-200/60 py-5">
        <div className="max-w-[1400px] mx-auto px-8 flex items-center justify-between text-xs text-neutral-400">
          <span>HAIRA v2</span>
          <span>Hair Product Intelligence</span>
        </div>
      </footer>

      {/* Global Search */}
      <GlobalSearch open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  );
}
