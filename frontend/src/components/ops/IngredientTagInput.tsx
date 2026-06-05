import { useState, useRef, useEffect, useCallback } from "react";
import { fetchIngredients } from "../../lib/api";
import type { IngredientSummary } from "../../types/api";

interface IngredientTagInputProps {
  value: string[];
  onChange: (ingredients: string[]) => void;
}

export default function IngredientTagInput({ value, onChange }: IngredientTagInputProps) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<IngredientSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Search ingredients with debounce
  const search = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    try {
      const results = await fetchIngredients(q);
      // Filter out already-added ingredients
      const filtered = results.filter(
        (r) => !value.some((v) => v.toLowerCase() === r.canonical_name.toLowerCase()),
      );
      setSuggestions(filtered.slice(0, 10));
      setHighlightIdx(-1);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, [value]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(query), 250);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, search]);

  // Click outside to close
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const addIngredient = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    if (value.some((v) => v.toLowerCase() === trimmed.toLowerCase())) return;
    onChange([...value, trimmed]);
    setQuery("");
    setSuggestions([]);
    setShowDropdown(false);
    inputRef.current?.focus();
  };

  const removeIngredient = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (highlightIdx >= 0 && suggestions[highlightIdx]) {
        addIngredient(suggestions[highlightIdx].canonical_name);
      } else if (query.trim()) {
        // Allow adding custom ingredient not in suggestions
        addIngredient(query);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Backspace" && !query && value.length > 0) {
      removeIngredient(value.length - 1);
    } else if (e.key === "Escape") {
      setShowDropdown(false);
    } else if (e.key === "," || e.key === ";") {
      e.preventDefault();
      if (query.trim()) addIngredient(query);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      {/* Tags + input */}
      <div
        className="flex flex-wrap gap-1.5 rounded-lg border border-cream-dark bg-cream p-2 min-h-[42px] cursor-text focus-within:border-ink focus-within:bg-white transition-colors"
        onClick={() => inputRef.current?.focus()}
      >
        {value.map((ing, i) => (
          <span
            key={`${ing}-${i}`}
            className="inline-flex items-center gap-1 rounded-md bg-white border border-cream-dark px-2 py-0.5 text-xs text-ink"
          >
            <span className="max-w-[200px] truncate">{ing}</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeIngredient(i); }}
              className="text-ink-muted hover:text-red-500 transition-colors ml-0.5"
            >
              ×
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setShowDropdown(true); }}
          onFocus={() => setShowDropdown(true)}
          onKeyDown={handleKeyDown}
          placeholder={value.length === 0 ? "Digite para buscar ingredientes..." : "Adicionar mais..."}
          className="flex-1 min-w-[120px] bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted/50"
        />
      </div>

      {/* Dropdown */}
      {showDropdown && (query.length >= 2 || loading) && (
        <div className="absolute z-40 mt-1 w-full rounded-lg border border-cream-dark bg-white shadow-lg max-h-60 overflow-y-auto">
          {loading && (
            <div className="px-3 py-2 text-xs text-ink-muted">Buscando...</div>
          )}
          {!loading && suggestions.length === 0 && query.length >= 2 && (
            <div className="px-3 py-2">
              <p className="text-xs text-ink-muted">Nenhum ingrediente encontrado</p>
              <button
                type="button"
                onMouseDown={(e) => { e.preventDefault(); addIngredient(query); }}
                className="mt-1 text-xs text-blue-500 hover:text-blue-700"
              >
                Adicionar "{query}" como novo →
              </button>
            </div>
          )}
          {suggestions.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); addIngredient(s.canonical_name); }}
              className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors ${
                i === highlightIdx ? "bg-cream" : "hover:bg-cream/50"
              }`}
            >
              <div className="min-w-0">
                <span className="font-medium text-ink">{s.canonical_name}</span>
                {s.inci_name && s.inci_name !== s.canonical_name && (
                  <span className="ml-2 text-xs text-ink-muted">({s.inci_name})</span>
                )}
              </div>
              <div className="flex items-center gap-2 ml-2 shrink-0">
                {s.category && (
                  <span className="text-[10px] rounded bg-cream-dark/50 px-1.5 py-0.5 text-ink-muted">{s.category}</span>
                )}
                <span className="text-[10px] text-ink-muted tabular-nums">{s.product_count} prod.</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Count */}
      <div className="mt-1 flex items-center justify-between">
        <span className="text-[10px] text-ink-muted">
          {value.length} ingrediente{value.length !== 1 ? "s" : ""}
          {value.length > 0 && " · Use ⌫ para remover o último"}
        </span>
        <span className="text-[10px] text-ink-muted">
          vírgula ou Enter para adicionar
        </span>
      </div>
    </div>
  );
}
