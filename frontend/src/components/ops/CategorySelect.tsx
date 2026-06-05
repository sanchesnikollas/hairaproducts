const CATEGORIES = [
  { value: "", label: "Sem categoria" },
  { value: "shampoo", label: "Shampoo" },
  { value: "condicionador", label: "Condicionador" },
  { value: "mascara", label: "Máscara" },
  { value: "tratamento", label: "Tratamento" },
  { value: "leave_in", label: "Leave-in" },
  { value: "oleo_serum", label: "Óleo / Sérum" },
  { value: "styling", label: "Styling" },
  { value: "coloracao", label: "Coloração" },
  { value: "transformacao", label: "Transformação" },
  { value: "kit", label: "Kit" },
];

interface CategorySelectProps {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}

export default function CategorySelect({ value, onChange, className }: CategorySelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={className ?? "w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink transition-colors"}
    >
      {CATEGORIES.map((c) => (
        <option key={c.value} value={c.value}>{c.label}</option>
      ))}
    </select>
  );
}
