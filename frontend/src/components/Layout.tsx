import { NavLink, Outlet } from 'react-router-dom';
import { motion } from 'motion/react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: dashboardIcon },
  { to: '/products', label: 'Products', icon: productIcon },
  { to: '/quarantine', label: 'Quarantine', icon: quarantineIcon },
];

function dashboardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12h4l3-9 4 18 3-9h4" />
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

export default function Layout() {
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

          <nav className="flex items-center gap-1">
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
                    `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-champagne/15 text-champagne-dark'
                        : 'text-ink-muted hover:text-ink hover:bg-ink/3'
                    }`
                  }
                >
                  <item.icon />
                  {item.label}
                </NavLink>
              </motion.div>
            ))}
          </nav>
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
    </div>
  );
}
