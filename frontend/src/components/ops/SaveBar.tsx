import { motion, AnimatePresence } from "motion/react";

interface SaveBarProps {
  isDirty: boolean;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
}

export default function SaveBar({ isDirty, saving, onSave, onDiscard }: SaveBarProps) {
  return (
    <AnimatePresence>
      {isDirty && (
        <motion.div
          initial={{ y: -48, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -48, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="sticky top-0 z-50 flex items-center justify-between rounded-lg bg-ink px-4 py-2.5 shadow-lg"
        >
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            <span className="text-sm text-white/80">Alterações não salvas</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onDiscard}
              disabled={saving}
              className="rounded-md border border-white/20 px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 disabled:opacity-50 transition-colors"
            >
              Descartar
            </button>
            <button
              onClick={onSave}
              disabled={saving}
              className="rounded-md bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
