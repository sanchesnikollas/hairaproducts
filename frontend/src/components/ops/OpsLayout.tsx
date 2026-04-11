import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { LayoutDashboard, Package, FlaskConical, Settings, LogOut, Tags, Award, Zap } from "lucide-react";

const NAV_ITEMS = [
  { to: "/ops", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/ops/brands", icon: Tags, label: "Marcas" },
  { to: "/ops/products", icon: Package, label: "Produtos" },
  { to: "/ops/quick-fill", icon: Zap, label: "Preencher" },
  { to: "/ops/seals", icon: Award, label: "Selos" },
  { to: "/ops/ingredients", icon: FlaskConical, label: "Ingredientes", admin: true },
  { to: "/ops/settings", icon: Settings, label: "Configurações", admin: true },
];

export default function OpsLayout() {
  const { user, loading, logout, isAdmin } = useAuth();

  if (loading) return <div className="flex h-screen items-center justify-center text-ink-muted">Carregando...</div>;
  if (!user) return <Navigate to="/login" replace />;

  const visibleItems = NAV_ITEMS.filter((item) => !item.admin || isAdmin);

  return (
    <div className="flex h-screen bg-cream">
      <aside className="flex w-56 flex-col border-r border-cream-dark bg-white">
        <div className="border-b border-cream-dark px-4 py-4">
          <h2 className="text-sm font-semibold text-ink">HAIRA</h2>
          <p className="text-xs text-ink-muted">{user.name} ({user.role})</p>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {visibleItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive ? "bg-cream font-medium text-ink" : "text-ink-muted hover:bg-cream hover:text-ink"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-cream-dark p-2">
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-cream hover:text-ink"
          >
            <LogOut size={16} />
            Sair
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
