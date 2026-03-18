import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { createUser, getUsers } from "../../lib/ops-api";
import { useAuth } from "../../lib/auth";
import type { OpsUser } from "../../types/ops";

export default function OpsSettings() {
  const { isAdmin } = useAuth();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ email: "", password: "", name: "", role: "reviewer" });
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState("");

  const { data: users, loading, refetch } = useAPI<(OpsUser & { is_active?: boolean })[]>(() => getUsers(), []);

  if (!isAdmin) return <Navigate to="/ops" replace />;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setCreating(true);
    try {
      await createUser(formData);
      setFormData({ email: "", password: "", name: "", role: "reviewer" });
      setShowForm(false);
      refetch();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Erro ao criar usuario");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink">Configuracoes</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          {showForm ? "Cancelar" : "Novo Usuario"}
        </button>
      </div>

      {/* Create user form */}
      {showForm && (
        <div className="rounded-xl border border-cream-dark bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold text-ink">Criar Usuario</h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-ink-muted">Nome</label>
                <input
                  type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm outline-none focus:border-ink"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-ink-muted">Email</label>
                <input
                  type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm outline-none focus:border-ink"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-ink-muted">Senha</label>
                <input
                  type="password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm outline-none focus:border-ink"
                  required minLength={6}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-ink-muted">Role</label>
                <select
                  value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm outline-none"
                >
                  <option value="reviewer">Reviewer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            {formError && <p className="text-sm text-coral">{formError}</p>}
            <button
              type="submit" disabled={creating}
              className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {creating ? "Criando..." : "Criar Usuario"}
            </button>
          </form>
        </div>
      )}

      {/* Users list */}
      <div className="rounded-xl border border-cream-dark bg-white">
        <div className="border-b border-cream-dark px-5 py-3">
          <h2 className="text-sm font-semibold text-ink">Usuarios</h2>
        </div>
        {loading ? (
          <p className="p-5 text-ink-muted">Carregando...</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-cream-dark text-left text-xs text-ink-muted uppercase tracking-wider">
                <th className="px-5 py-3">Nome</th>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id} className="border-b border-cream-dark/50 hover:bg-cream/50">
                  <td className="px-5 py-3 font-medium text-ink">{u.name}</td>
                  <td className="px-5 py-3 text-ink-muted">{u.email}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.role === "admin" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
                    }`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-xs ${u.is_active !== false ? "text-emerald-600" : "text-red-500"}`}>
                      {u.is_active !== false ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
