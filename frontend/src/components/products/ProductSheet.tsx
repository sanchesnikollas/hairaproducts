import { useState, useEffect, useCallback } from 'react';
import { ExternalLink } from 'lucide-react';
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import StatusBadge from '@/components/StatusBadge';
import { getProduct, updateProduct } from '@/lib/api';
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

  // Fetch full product detail when ID changes
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
      // Re-fetch full product to get all fields (PATCH returns partial)
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
      ? 'text-ink-muted'
      : qualityScore === 100
        ? 'text-sage'
        : qualityScore >= 70
          ? 'text-amber'
          : 'text-coral';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-[500px] p-0 overflow-hidden z-[60]">
        <ScrollArea className="h-full">
          <div className="p-6 space-y-6">
            {loading || !product ? (
              <div className="flex items-center justify-center py-24">
                <span className="text-sm text-ink-muted">Loading...</span>
              </div>
            ) : (
              <>
                {/* Header */}
                <SheetHeader className="p-0 space-y-4">
                  {product.image_url_main && (
                    <img
                      src={product.image_url_main}
                      alt={product.product_name}
                      className="w-full max-h-[200px] object-contain rounded-lg bg-cream"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  )}
                  <div className="space-y-2">
                    <SheetTitle className="font-display text-xl font-semibold text-ink leading-tight">
                      {sanitizeText(product.product_name)}
                    </SheetTitle>
                    <SheetDescription className="flex items-center gap-2">
                      <span className="text-sm text-ink-muted">
                        {formatBrandName(product.brand_slug)}
                      </span>
                      <StatusBadge status={product.verification_status} />
                    </SheetDescription>
                  </div>
                </SheetHeader>

                <Separator />

                {/* Basic Info */}
                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    Basic Info
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <InfoItem label="Category" value={product.product_category} />
                    <InfoItem label="Type" value={product.product_type_normalized} />
                    <InfoItem label="Gender" value={product.gender_target} />
                    <InfoItem
                      label="Price"
                      value={
                        product.price
                          ? `${product.currency ?? 'R$'} ${product.price.toFixed(2)}`
                          : null
                      }
                    />
                    <InfoItem label="Size" value={product.size_volume} />
                    <InfoItem label="Line" value={product.line_collection} />
                  </div>
                  {product.product_url && (
                    <a
                      href={product.product_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs text-champagne-dark hover:underline"
                    >
                      <ExternalLink className="size-3" />
                      View product page
                    </a>
                  )}
                </section>

                <Separator />

                {/* INCI Ingredients */}
                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    INCI Ingredients
                    {product.inci_ingredients && (
                      <span className="ml-2 text-ink-muted font-normal normal-case">
                        ({product.inci_ingredients.length})
                      </span>
                    )}
                  </h3>
                  {product.inci_ingredients && product.inci_ingredients.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5 max-h-[200px] overflow-y-auto">
                      {product.inci_ingredients.map((ingredient, i) => (
                        <Badge
                          key={i}
                          variant="secondary"
                          className="text-[11px] font-normal"
                        >
                          {ingredient}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-ink-faint">No INCI data available</p>
                  )}
                </section>

                <Separator />

                {/* Labels / Seals */}
                {product.product_labels && (
                  <>
                    <section className="space-y-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                        Labels & Seals
                      </h3>
                      {(product.product_labels.detected?.length > 0 ||
                        product.product_labels.inferred?.length > 0) ? (
                        <div className="space-y-2">
                          {product.product_labels.detected?.length > 0 && (
                            <div>
                              <span className="text-[10px] uppercase tracking-wider text-ink-faint mb-1 block">
                                Detected
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {product.product_labels.detected.map((seal) => (
                                  <Badge
                                    key={seal}
                                    className={
                                      POSITIVE_SEALS.has(seal)
                                        ? 'bg-sage-bg text-sage border-sage/20'
                                        : 'bg-coral-bg text-coral border-coral/20'
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
                              <span className="text-[10px] uppercase tracking-wider text-ink-faint mb-1 block">
                                Inferred
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {product.product_labels.inferred.map((seal) => (
                                  <Badge
                                    key={seal}
                                    className={
                                      POSITIVE_SEALS.has(seal)
                                        ? 'bg-sage-bg text-sage border-sage/20'
                                        : 'bg-coral-bg text-coral border-coral/20'
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
                        <p className="text-sm text-ink-faint">No labels detected</p>
                      )}
                    </section>
                    <Separator />
                  </>
                )}

                {/* Quality */}
                {product.quality && (
                  <>
                    <section className="space-y-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                        Quality
                      </h3>
                      <div className="flex items-baseline gap-2">
                        <span className={`text-2xl font-display font-semibold tabular-nums ${qualityColor}`}>
                          {qualityScore}
                        </span>
                        <span className="text-sm text-ink-muted">/ 100</span>
                      </div>
                      {product.quality.issues.length > 0 && (
                        <div className="space-y-1.5 max-h-[150px] overflow-y-auto">
                          {product.quality.issues.map((issue, i) => (
                            <div
                              key={i}
                              className={`text-xs px-2.5 py-1.5 rounded-md ${
                                issue.severity === 'error'
                                  ? 'bg-coral-bg text-coral'
                                  : issue.severity === 'warning'
                                    ? 'bg-amber-bg text-amber'
                                    : 'bg-ink/5 text-ink-muted'
                              }`}
                            >
                              <span className="font-medium">{issue.field}:</span>{' '}
                              {issue.message}
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                    <Separator />
                  </>
                )}

                {/* Evidence */}
                {product.evidence && product.evidence.length > 0 && (
                  <>
                    <section className="space-y-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                        Evidence ({product.evidence.length})
                      </h3>
                      <div className="space-y-2 max-h-[200px] overflow-y-auto">
                        {product.evidence.map((ev) => (
                          <div
                            key={ev.id}
                            className="text-xs p-2.5 rounded-md bg-ink/3 space-y-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-ink">
                                {ev.field_name}
                              </span>
                              <span className="text-ink-faint">
                                {ev.extraction_method}
                              </span>
                            </div>
                            {ev.source_url && (
                              <a
                                href={ev.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-champagne-dark hover:underline truncate block"
                              >
                                {ev.source_url}
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    </section>
                    <Separator />
                  </>
                )}

                {/* Edit Section */}
                <section className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                      Edit Product
                    </h3>
                    {!editing && (
                      <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                        Edit
                      </Button>
                    )}
                  </div>

                  {editing && (
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
                        <label className="text-xs font-medium text-ink-muted">
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

                      <div className="flex items-center gap-2 pt-2">
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
                </section>
              </>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

function InfoItem({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <span className="text-xs text-ink-faint">{label}</span>
      <p className="text-sm text-ink truncate">{value || '--'}</p>
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
      <label className="text-xs font-medium text-ink-muted">{label}</label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full"
      />
    </div>
  );
}
