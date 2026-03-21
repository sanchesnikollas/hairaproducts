import { useState, useEffect, useCallback } from 'react';
import {
  ExternalLink,
  Package,
  FlaskConical,
  Shield,
  AlertTriangle,
  FileText,
  Pencil,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import StatusBadge from '@/components/StatusBadge';
import { getProduct, updateProduct, getQuarantine, approveQuarantine, rejectQuarantine } from '@/lib/api';
import type { Product } from '@/types/api';

// ── Seal Display Config ──

const SEAL_DISPLAY: Record<string, { label: string }> = {
  sulfate_free: { label: 'Sulfate Free' },
  paraben_free: { label: 'Paraben Free' },
  silicone_free: { label: 'Silicone Free' },
  fragrance_free: { label: 'Fragrance Free' },
  petrolatum_free: { label: 'Petrolatum Free' },
  dye_free: { label: 'Dye Free' },
  vegan: { label: 'Vegan' },
  cruelty_free: { label: 'Cruelty Free' },
  organic: { label: 'Organic' },
  natural: { label: 'Natural' },
  hypoallergenic: { label: 'Hypoallergenic' },
  dermatologically_tested: { label: 'Derm. Tested' },
  ophthalmologically_tested: { label: 'Ophth. Tested' },
  uv_protection: { label: 'UV Protection' },
  thermal_protection: { label: 'Thermal Protection' },
  low_poo: { label: 'Low Poo' },
  no_poo: { label: 'No Poo' },
};

const POSITIVE_SEALS = new Set([
  'sulfate_free', 'paraben_free', 'silicone_free', 'fragrance_free',
  'petrolatum_free', 'dye_free', 'vegan', 'cruelty_free', 'organic',
  'natural', 'hypoallergenic', 'low_poo', 'no_poo',
]);

function formatBrandName(slug: string): string {
  return slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function formatFieldValue(value: string | null | undefined): string {
  if (!value || value === 'unknown') return '--';
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function sanitizeText(text: string): string {
  if (!text) return text;
  const doc = new DOMParser().parseFromString(text, 'text/html');
  return (doc.body.textContent ?? '').replace(/\s+/g, ' ').trim();
}

interface ProductSheetProps {
  productId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onProductUpdated: () => void;
}

export default function ProductSheet({
  productId,
  open,
  onOpenChange,
  onProductUpdated,
}: ProductSheetProps) {
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editForm, setEditForm] = useState({
    product_name: '',
    description: '',
    product_category: '',
    product_type_normalized: '',
    gender_target: '',
    verification_status: '',
  });

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    info: false,
    inci: true,
    labels: false,
    quality: false,
    evidence: false,
    edit: false,
  });

  const toggleSection = (key: string) => {
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    if (!productId || !open) {
      setProduct(null);
      setEditing(false);
      return;
    }
    setLoading(true);
    getProduct(productId)
      .then((p) => {
        setProduct(p);
        setEditForm({
          product_name: p.product_name || '',
          description: p.description || '',
          product_category: p.product_category || '',
          product_type_normalized: p.product_type_normalized || '',
          gender_target: p.gender_target || '',
          verification_status: p.verification_status || '',
        });
      })
      .catch(() => toast.error('Failed to load product details'))
      .finally(() => setLoading(false));
  }, [productId, open]);

  const handleSave = useCallback(async () => {
    if (!product) return;
    setSaving(true);
    try {
      await updateProduct(product.id, editForm);
      const refreshed = await getProduct(product.id);
      setProduct(refreshed);
      setEditForm({
        product_name: refreshed.product_name || '',
        description: refreshed.description || '',
        product_category: refreshed.product_category || '',
        product_type_normalized: refreshed.product_type_normalized || '',
        gender_target: refreshed.gender_target || '',
        verification_status: refreshed.verification_status || '',
      });
      setEditing(false);
      onProductUpdated();
      toast.success('Product updated successfully');
    } catch {
      toast.error('Failed to update product');
    } finally {
      setSaving(false);
    }
  }, [product, editForm, onProductUpdated]);

  const qualityScore = product?.quality?.score;
  const qualityColor =
    qualityScore === undefined
      ? 'text-neutral-400'
      : qualityScore === 100
        ? 'text-emerald-600'
        : qualityScore >= 70
          ? 'text-amber-600'
          : 'text-red-500';

  const qualityBgColor =
    qualityScore === undefined
      ? 'bg-neutral-50 border-neutral-200'
      : qualityScore === 100
        ? 'bg-emerald-50 border-emerald-200'
        : qualityScore >= 70
          ? 'bg-amber-50 border-amber-200'
          : 'bg-red-50 border-red-200';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-[480px] p-0 overflow-hidden border-l border-neutral-200">
        <ScrollArea className="h-full">
          {loading ? (
            <SheetLoadingSkeleton />
          ) : !product ? (
            <div className="flex items-center justify-center py-24">
              <span className="text-sm text-neutral-400">No product selected</span>
            </div>
          ) : (
            <div className="pb-8">
              {/* Header: image thumbnail + title side by side */}
              <div className="px-5 pt-5 pb-4 border-b border-neutral-100">
                <div className="flex gap-4">
                  {/* Thumbnail */}
                  <div className="shrink-0 w-20 h-20 rounded-lg bg-neutral-50 border border-neutral-100 overflow-hidden flex items-center justify-center">
                    {product.image_url_main ? (
                      <img
                        src={product.image_url_main}
                        alt={product.product_name}
                        className="w-full h-full object-contain p-1.5"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                          (e.target as HTMLImageElement).parentElement!.innerHTML =
                            '<div class="text-neutral-300 flex items-center justify-center w-full h-full"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg></div>';
                        }}
                      />
                    ) : (
                      <Package className="size-6 text-neutral-300" />
                    )}
                  </div>

                  {/* Title + brand */}
                  <SheetHeader className="flex-1 min-w-0 space-y-0 p-0">
                    <SheetTitle className="text-[15px] font-semibold text-neutral-900 leading-snug line-clamp-2">
                      {sanitizeText(product.product_name)}
                    </SheetTitle>
                    <SheetDescription className="flex items-center gap-1.5 mt-1">
                      <span className="text-sm text-neutral-500">
                        {formatBrandName(product.brand_slug)}
                      </span>
                      {product.line_collection && (
                        <>
                          <span className="text-neutral-300">·</span>
                          <span className="text-sm text-neutral-400">
                            {product.line_collection}
                          </span>
                        </>
                      )}
                    </SheetDescription>
                    <div className="pt-1.5">
                      <StatusBadge status={product.verification_status} size="sm" />
                    </div>
                  </SheetHeader>
                </div>

                {/* Stat pills */}
                <div className="flex items-center gap-2 mt-3 flex-wrap">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium ${qualityBgColor} ${qualityColor}`}>
                    {qualityScore ?? '--'} <span className="font-normal text-[10px] opacity-60">quality</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-neutral-200 bg-neutral-50 text-xs font-medium text-neutral-700">
                    {product.inci_ingredients?.length ?? 0} <span className="font-normal text-[10px] text-neutral-400">INCI</span>
                  </span>
                  {product.price != null && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded border border-neutral-200 bg-neutral-50 text-xs font-medium text-neutral-700">
                      {product.currency ?? 'BRL'} {product.price.toFixed(2)}
                    </span>
                  )}
                  {product.product_url && (
                    <a
                      href={product.product_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-neutral-200 bg-white text-xs text-neutral-400 hover:text-neutral-600 hover:border-neutral-300 transition-colors ml-auto"
                    >
                      <ExternalLink className="size-3" />
                      <span>Abrir</span>
                    </a>
                  )}
                </div>
              </div>

              {/* Sections */}
              <div className="px-5 pt-1 space-y-0">
                {/* Basic Info */}
                <CollapsibleSection
                  title="Basic Info"
                  icon={<Package className="size-3.5" />}
                  expanded={expandedSections.info}
                  onToggle={() => toggleSection('info')}
                  status={product.description ? 'ok' : 'warning'}
                >
                  <div className="space-y-2.5">
                    <div className="grid grid-cols-2 gap-2">
                      <InfoItem label="Category" value={formatFieldValue(product.product_category)} />
                      <InfoItem label="Type" value={formatFieldValue(product.product_type_normalized)} />
                      <InfoItem label="Gender" value={formatFieldValue(product.gender_target)} />
                      <InfoItem label="Size" value={product.size_volume || '--'} />
                    </div>
                    {product.description && (
                      <div className="pt-2 border-t border-neutral-100">
                        <p className="text-[13px] text-neutral-500 leading-relaxed line-clamp-4">
                          {sanitizeText(product.description)}
                        </p>
                      </div>
                    )}
                  </div>
                </CollapsibleSection>

                {/* INCI Ingredients */}
                <CollapsibleSection
                  title={`INCI Ingredients (${product.inci_ingredients?.length ?? 0})`}
                  icon={<FlaskConical className="size-3.5" />}
                  expanded={expandedSections.inci}
                  onToggle={() => toggleSection('inci')}
                  status={product.inci_ingredients && product.inci_ingredients.length > 0 ? 'ok' : 'warning'}
                >
                  {product.inci_ingredients && product.inci_ingredients.length > 0 ? (
                    <div className="flex flex-wrap gap-1 max-h-[260px] overflow-y-auto">
                      {product.inci_ingredients.map((ingredient, i) => (
                        <span
                          key={i}
                          className="text-[11px] bg-neutral-100 text-neutral-600 px-2 py-0.5 rounded"
                        >
                          {ingredient}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-neutral-400">No INCI data available</p>
                  )}
                </CollapsibleSection>

                {/* Labels / Seals */}
                {product.product_labels && (
                  <CollapsibleSection
                    title="Labels & Seals"
                    icon={<Shield className="size-3.5" />}
                    expanded={expandedSections.labels}
                    onToggle={() => toggleSection('labels')}
                    status={(product.product_labels?.detected?.length || product.product_labels?.inferred?.length) ? 'ok' : 'warning'}
                  >
                    {(product.product_labels.detected?.length > 0 ||
                      product.product_labels.inferred?.length > 0) ? (
                      <div className="space-y-3">
                        {product.product_labels.detected?.length > 0 && (
                          <div>
                            <span className="text-[10px] uppercase tracking-wider text-neutral-400 mb-1.5 block font-medium">
                              Detected
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {product.product_labels.detected.map((seal) => (
                                <Badge
                                  key={seal}
                                  className={
                                    POSITIVE_SEALS.has(seal)
                                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                      : 'bg-red-50 text-red-600 border-red-200'
                                  }
                                  variant="outline"
                                >
                                  {SEAL_DISPLAY[seal]?.label ?? seal}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                        {product.product_labels.inferred?.length > 0 && (
                          <div>
                            <span className="text-[10px] uppercase tracking-wider text-neutral-400 mb-1.5 block font-medium">
                              Inferred from INCI
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {product.product_labels.inferred.map((seal) => (
                                <Badge
                                  key={seal}
                                  className={
                                    POSITIVE_SEALS.has(seal)
                                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                      : 'bg-red-50 text-red-600 border-red-200'
                                  }
                                  variant="outline"
                                >
                                  {SEAL_DISPLAY[seal]?.label ?? seal}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-sm text-neutral-400">No labels detected</p>
                    )}
                  </CollapsibleSection>
                )}

                {/* Quality */}
                {product.quality && (
                  <CollapsibleSection
                    title="Quality Report"
                    icon={<AlertTriangle className="size-3.5" />}
                    expanded={expandedSections.quality}
                    onToggle={() => toggleSection('quality')}
                    badge={
                      product.quality.issues.length > 0
                        ? `${product.quality.error_count}E / ${product.quality.warning_count}W`
                        : undefined
                    }
                  >
                    {product.quality.issues.length > 0 ? (
                      <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
                        {product.quality.issues.map((issue, i) => (
                          <div
                            key={i}
                            className={`text-xs px-3 py-2 rounded-lg flex items-start gap-2 ${
                              issue.severity === 'error'
                                ? 'bg-red-50 text-red-600 border border-red-100'
                                : issue.severity === 'warning'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-100'
                                  : 'bg-neutral-50 text-neutral-500 border border-neutral-100'
                            }`}
                          >
                            <span className="font-medium shrink-0">{issue.field}:</span>
                            <span>{issue.message}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-emerald-600">All quality checks passed</p>
                    )}
                  </CollapsibleSection>
                )}

                {/* Evidence */}
                {product.evidence && product.evidence.length > 0 && (
                  <CollapsibleSection
                    title={`Evidence (${product.evidence.length})`}
                    icon={<FileText className="size-3.5" />}
                    expanded={expandedSections.evidence}
                    onToggle={() => toggleSection('evidence')}
                  >
                    <div className="space-y-2 max-h-[250px] overflow-y-auto">
                      {product.evidence.map((ev) => (
                        <div
                          key={ev.id}
                          className="text-xs p-3 rounded-lg bg-neutral-50 border border-neutral-100 space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-neutral-700">
                              {ev.field_name}
                            </span>
                            <Badge variant="outline" className="text-[10px] h-auto py-0 px-1.5 border-neutral-200 text-neutral-400">
                              {ev.extraction_method}
                            </Badge>
                          </div>
                          {ev.source_url && (
                            <a
                              href={ev.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-neutral-400 hover:text-neutral-600 hover:underline truncate block"
                            >
                              {ev.source_url}
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </CollapsibleSection>
                )}

                {/* Edit Section */}
                <CollapsibleSection
                  title="Edit Product"
                  icon={<Pencil className="size-3.5" />}
                  expanded={expandedSections.edit || editing}
                  onToggle={() => {
                    if (!editing) toggleSection('edit');
                  }}
                >
                  {!editing ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditing(true);
                        setExpandedSections((prev) => ({ ...prev, edit: true }));
                      }}
                    >
                      <Pencil className="size-3 mr-1.5" />
                      Start Editing
                    </Button>
                  ) : (
                    <div className="space-y-3">
                      <EditField
                        label="Product Name"
                        value={editForm.product_name}
                        onChange={(v) =>
                          setEditForm((f) => ({ ...f, product_name: v }))
                        }
                      />
                      <EditField
                        label="Description"
                        value={editForm.description}
                        onChange={(v) =>
                          setEditForm((f) => ({ ...f, description: v }))
                        }
                      />
                      <EditField
                        label="Category"
                        value={editForm.product_category}
                        onChange={(v) =>
                          setEditForm((f) => ({ ...f, product_category: v }))
                        }
                      />
                      <EditField
                        label="Type"
                        value={editForm.product_type_normalized}
                        onChange={(v) =>
                          setEditForm((f) => ({ ...f, product_type_normalized: v }))
                        }
                      />
                      <EditField
                        label="Gender Target"
                        value={editForm.gender_target}
                        onChange={(v) =>
                          setEditForm((f) => ({ ...f, gender_target: v }))
                        }
                      />

                      <div className="space-y-1.5">
                        <label className="text-xs font-medium text-neutral-500">
                          Verification Status
                        </label>
                        <Select
                          value={editForm.verification_status}
                          onValueChange={(v) =>
                            setEditForm((f) => ({ ...f, verification_status: v ?? '' }))
                          }
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="verified_inci">Verified INCI</SelectItem>
                            <SelectItem value="catalog_only">Catalog Only</SelectItem>
                            <SelectItem value="quarantined">Quarantined</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <Separator />

                      <div className="flex items-center gap-2">
                        <Button onClick={handleSave} disabled={saving} size="sm">
                          {saving ? 'Saving...' : 'Save Changes'}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEditing(false)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </CollapsibleSection>
              </div>

              {/* Quarantine Footer Actions */}
              {product.verification_status === 'quarantined' && (
                <QuarantineActions productId={product.id} productName={product.product_name} onAction={onProductUpdated} />
              )}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ── Sub-components ──

function CollapsibleSection({
  title,
  icon,
  expanded,
  onToggle,
  badge,
  status,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  badge?: string;
  status?: 'ok' | 'warning' | 'missing';
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-neutral-100 last:border-0">
      <button
        className="flex items-center gap-2.5 w-full py-3 text-left hover:bg-neutral-50/50 transition-colors rounded-md"
        onClick={onToggle}
      >
        <span className="text-neutral-400">{icon}</span>
        <span className="text-[12px] font-medium text-neutral-500 flex-1">
          {title}
        </span>
        {status === 'ok' && (
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
        )}
        {status === 'warning' && (
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
        )}
        {badge && (
          <span className="text-[10px] text-neutral-400 font-medium">
            {badge}
          </span>
        )}
        {expanded ? (
          <ChevronUp className="size-3.5 text-neutral-300" />
        ) : (
          <ChevronDown className="size-3.5 text-neutral-300" />
        )}
      </button>
      {expanded && <div className="pb-4 pt-1">{children}</div>}
    </div>
  );
}

function SheetLoadingSkeleton() {
  return (
    <div className="p-5 space-y-5">
      <div className="flex gap-4">
        <Skeleton className="w-20 h-20 rounded-lg shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-4/5" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-5 w-20 rounded" />
        </div>
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-6 w-16 rounded" />
        <Skeleton className="h-6 w-16 rounded" />
        <Skeleton className="h-6 w-20 rounded" />
      </div>
      <Separator />
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full rounded" />
        ))}
      </div>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-neutral-50 rounded-md px-3 py-2">
      <span className="text-[10px] text-neutral-400 uppercase tracking-wider block">{label}</span>
      <span className="text-[13px] text-neutral-700 font-medium">{value}</span>
    </div>
  );
}

function QuarantineActions({
  productId,
  productName,
  onAction,
}: {
  productId: string;
  productName: string;
  onAction: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [confirmingReject, setConfirmingReject] = useState(false);

  async function handleApprove() {
    setBusy(true);
    try {
      const items = await getQuarantine('pending');
      const match = items.find((q) => q.product_id === productId);
      if (match) {
        await approveQuarantine(match.id);
        toast.success(`${productName} aprovado`);
        onAction();
      } else {
        toast.error('Registro de quarentena nao encontrado');
      }
    } catch {
      toast.error('Falha ao aprovar');
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    if (!confirmingReject) {
      setConfirmingReject(true);
      return;
    }
    setBusy(true);
    try {
      const items = await getQuarantine('pending');
      const match = items.find((q) => q.product_id === productId);
      if (match) {
        await rejectQuarantine(match.id);
        toast.success(`${productName} rejeitado`);
        onAction();
      } else {
        toast.error('Registro de quarentena nao encontrado');
      }
    } catch {
      toast.error('Falha ao rejeitar');
    } finally {
      setBusy(false);
      setConfirmingReject(false);
    }
  }

  return (
    <div className="sticky bottom-0 px-5 py-3 bg-white border-t border-neutral-100 flex items-center gap-3">
      <Button onClick={handleApprove} disabled={busy} className="flex-1">
        {busy ? 'Processando...' : 'Aprovar'}
      </Button>
      <Button
        variant={confirmingReject ? 'destructive' : 'outline'}
        onClick={handleReject}
        onBlur={() => setConfirmingReject(false)}
        disabled={busy}
        className="flex-1"
      >
        {confirmingReject ? 'Confirmar Rejeicao' : 'Rejeitar'}
      </Button>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-neutral-500">{label}</label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full"
      />
    </div>
  );
}
