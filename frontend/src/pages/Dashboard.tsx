import { useMemo } from 'react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { useAPI } from '@/hooks/useAPI'
import { getBrands, getProducts, getQuarantine } from '@/lib/api'
import { ErrorState } from '@/components/LoadingState'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// ── Color Tokens ──

const COLORS = {
  sage: '#7A9E7E',
  champagne: '#C9A96E',
  coral: '#C27C6B',
  amber: '#C9A040',
  ink: '#1A1714',
  inkMuted: '#7A7068',
  inkFaint: '#B8AFA6',
}

// ── Seal Label Display Names ──

const SEAL_LABELS: Record<string, string> = {
  sulfate_free: 'Sulfate Free',
  paraben_free: 'Paraben Free',
  silicone_free: 'Silicone Free',
  fragrance_free: 'Fragrance Free',
  petrolatum_free: 'Petrolatum Free',
  dye_free: 'Dye Free',
  vegan: 'Vegan',
  cruelty_free: 'Cruelty Free',
  organic: 'Organic',
  natural: 'Natural',
  hypoallergenic: 'Hypoallergenic',
  dermatologically_tested: 'Derm. Tested',
  ophthalmologically_tested: 'Ophth. Tested',
  uv_protection: 'UV Protection',
  thermal_protection: 'Thermal Protection',
  low_poo: 'Low Poo',
  no_poo: 'No Poo',
}

const CATEGORY_LABELS: Record<string, string> = {
  shampoo: 'Shampoo',
  condicionador: 'Condicionador',
  mascara: 'Mascara',
  tratamento: 'Tratamento',
  leave_in: 'Leave-in',
  oleo_serum: 'Oleo & Serum',
  styling: 'Styling',
  coloracao: 'Coloracao',
}

// ── Custom Tooltip ──

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white rounded-xl shadow-lg border border-ink/5 px-4 py-3 text-sm">
      <p className="font-medium text-ink mb-1.5 capitalize">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-ink-muted">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.color }} />
          <span>{p.name}:</span>
          <span className="font-medium text-ink tabular-nums">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

// ── Skeleton Loaders ──

function KPISkeletons() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="shadow-sm">
          <CardContent className="pt-2">
            <div className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-xl" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-8 w-16" />
                <Skeleton className="h-3 w-12" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function MiddleSectionSkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="lg:col-span-2 shadow-sm">
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-3 w-60" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full rounded-lg" />
        </CardContent>
      </Card>
      <Card className="shadow-sm">
        <CardHeader>
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-3 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full rounded-lg" />
        </CardContent>
      </Card>
    </div>
  )
}

function BottomSectionSkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card className="shadow-sm">
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-3 w-56" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-56 w-full rounded-lg" />
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <Card className="shadow-sm"><CardContent className="pt-6"><Skeleton className="h-32 w-full rounded-lg" /></CardContent></Card>
        <Card className="shadow-sm"><CardContent className="pt-6"><Skeleton className="h-32 w-full rounded-lg" /></CardContent></Card>
      </div>
    </div>
  )
}

// ── SVG Icons ──

function PackageIcon({ className }: { className?: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M16.5 9.4l-9-5.19" />
      <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function ClipboardIcon({ className }: { className?: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    </svg>
  );
}

function AlertTriangleIcon({ className }: { className?: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

// ── Main Dashboard ──

export default function Dashboard() {
  const { data: brands, loading: brandsLoading, error: brandsError } = useAPI(getBrands)
  const { data: productsResponse, loading: productsLoading, error: productsError } = useAPI(
    () => getProducts({ verified_only: false, per_page: 1000 })
  )
  const { data: pendingQuarantine, loading: quarantineLoading } = useAPI(
    () => getQuarantine('pending')
  )

  const products = productsResponse?.items ?? null
  const loading = brandsLoading || productsLoading || quarantineLoading
  const error = brandsError || productsError

  const pendingCount = pendingQuarantine?.length ?? 0

  // ── Computed Stats (aggregated across all brands) ──

  const stats = useMemo(() => {
    if (!brands || brands.length === 0) return null
    const total = brands.reduce((sum, b) => sum + b.extracted_total, 0)
    const verified = brands.reduce((sum, b) => sum + b.verified_inci_total, 0)
    const catalog = brands.reduce((sum, b) => sum + b.catalog_only_total, 0)
    const quarantined = brands.reduce((sum, b) => sum + b.quarantined_total, 0)
    const discovered = brands.reduce((sum, b) => sum + b.discovered_total, 0)
    const hair = brands.reduce((sum, b) => sum + b.hair_total, 0)
    const rate = total > 0 ? (verified / total) * 100 : 0
    const above90 = brands.filter(b => b.verified_inci_rate >= 0.90 && b.extracted_total > 0).length
    return { total, verified, catalog, quarantined, discovered, hair, rate, above90, brandCount: brands.length }
  }, [brands])

  // ── Coverage Funnel ──

  const funnelData = useMemo(() => {
    if (!stats) return []
    return [
      { name: 'Discovered', value: stats.discovered },
      { name: 'Hair Products', value: stats.hair },
      { name: 'Extracted', value: stats.total },
      { name: 'Verified INCI', value: stats.verified },
    ]
  }, [stats])

  // ── Category Distribution ──

  const typeData = useMemo(() => {
    if (!products) return []
    const counts: Record<string, number> = {}
    products.forEach(p => {
      const t = p.product_category || 'Other'
      counts[t] = (counts[t] || 0) + 1
    })
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, value]) => ({ name: CATEGORY_LABELS[name] || name.charAt(0).toUpperCase() + name.slice(1), value }))
  }, [products])

  const typeColors = [
    COLORS.sage, COLORS.champagne, COLORS.coral, COLORS.amber,
    '#8B9DC3', '#A6854A', '#9B8EC2', COLORS.inkFaint,
  ]

  // ── Seal Distribution ──

  const sealDistributionData = useMemo(() => {
    if (!products) return []
    const counts: Record<string, number> = {}
    products.forEach(p => {
      if (!p.product_labels) return
      const allSeals = [...(p.product_labels.detected || []), ...(p.product_labels.inferred || [])]
      allSeals.forEach(seal => {
        counts[seal] = (counts[seal] || 0) + 1
      })
    })
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([key, count]) => ({
        name: SEAL_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        key,
        count,
      }))
  }, [products])

  // ── Render ──

  if (error) return <ErrorState message={error} />

  if (loading) {
    return (
      <div className="space-y-8 pb-12">
        <div className="space-y-2">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-4 w-80" />
        </div>
        <KPISkeletons />
        <MiddleSectionSkeleton />
        <BottomSectionSkeleton />
      </div>
    )
  }

  if (!stats) return null

  // ── Brand Tiers ──

  const brandTiers = useMemo(() => {
    if (!brands) return []
    const activeBrands = brands.filter(b => b.extracted_total > 0)
    const tiers = [
      { label: '>= 90%', brands: activeBrands.filter(b => b.verified_inci_rate >= 0.90), color: 'bg-sage', textColor: 'text-sage' },
      { label: '80-89%', brands: activeBrands.filter(b => b.verified_inci_rate >= 0.80 && b.verified_inci_rate < 0.90), color: 'bg-champagne', textColor: 'text-champagne-dark' },
      { label: '70-79%', brands: activeBrands.filter(b => b.verified_inci_rate >= 0.70 && b.verified_inci_rate < 0.80), color: 'bg-amber-400', textColor: 'text-amber-600' },
      { label: '< 70%', brands: activeBrands.filter(b => b.verified_inci_rate < 0.70), color: 'bg-coral', textColor: 'text-coral' },
    ]
    return tiers
  }, [brands])

  const kpiCards = [
    {
      label: 'Brands >=90%',
      value: stats.above90,
      percent: `of ${stats.brandCount}`,
      icon: <CheckCircleIcon className="text-sage" />,
      color: 'text-sage',
      bgColor: 'bg-sage/10',
    },
    {
      label: 'Total Products',
      value: stats.total,
      percent: `${stats.verified.toLocaleString()} with INCI`,
      icon: <PackageIcon className="text-ink" />,
      color: 'text-ink',
      bgColor: 'bg-ink/5',
    },
    {
      label: 'Catalog Only',
      value: stats.catalog,
      percent: `${Math.round((stats.catalog / stats.total) * 100)}%`,
      icon: <ClipboardIcon className="text-amber-600" />,
      color: 'text-amber-600',
      bgColor: 'bg-amber-50',
    },
    {
      label: 'Quarantined',
      value: stats.quarantined,
      percent: `${Math.round((stats.quarantined / stats.total) * 100)}%`,
      icon: <AlertTriangleIcon className="text-coral" />,
      color: 'text-coral',
      bgColor: 'bg-coral/10',
    },
  ]

  // Funnel step percentages
  const funnelWithPercent = funnelData.map((item, i) => {
    if (i === 0) return { ...item, percent: '' }
    const prev = funnelData[i - 1].value
    const pct = prev > 0 ? Math.round((item.value / prev) * 100) : 0
    return { ...item, percent: `${pct}%` }
  })

  return (
    <div className="space-y-8 pb-12">

      {/* ── Page Title ── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="font-display text-4xl font-semibold text-ink tracking-tight">
          HAIRA Dashboard
        </h1>
        <p className="text-ink-muted text-sm mt-1.5">
          {stats.brandCount} brands &middot; {stats.total.toLocaleString()} products &middot; {Math.round(stats.rate)}% INCI verified
        </p>
      </motion.div>

      {/* ── Section 1: KPI Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        {kpiCards.map((kpi, i) => (
          <motion.div
            key={kpi.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 + i * 0.07 }}
          >
            <Card className={cn(
              'shadow-sm hover:shadow-md transition-shadow duration-300 cursor-default'
            )}>
              <CardContent className="pt-2">
                <div className="flex items-start gap-3">
                  <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center shrink-0', kpi.bgColor)}>
                    {kpi.icon}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] uppercase tracking-[0.12em] font-semibold text-ink-muted truncate">
                      {kpi.label}
                    </p>
                    <p className="font-display text-3xl font-semibold text-ink leading-none mt-1 tabular-nums">
                      {kpi.value.toLocaleString()}
                    </p>
                    <p className="text-xs text-ink-muted mt-1">
                      {kpi.percent} of total
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* ── Brand INCI Tiers ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
      >
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="font-display text-xl font-semibold">INCI Coverage by Brand</CardTitle>
            <CardDescription>{stats.above90} of {stats.brandCount} brands above 90% target</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {brandTiers.map(tier => (
                <div key={tier.label} className="flex items-start gap-3">
                  <div className="flex items-center gap-2 w-20 shrink-0 pt-0.5">
                    <span className={cn('w-2.5 h-2.5 rounded-full shrink-0', tier.color)} />
                    <span className="text-xs font-semibold text-ink-muted">{tier.label}</span>
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={cn('text-sm font-semibold tabular-nums', tier.textColor)}>
                      {tier.brands.length}
                    </span>
                    {tier.brands.length > 0 && (
                      <span className="text-xs text-ink-muted">
                        — {tier.brands.map(b => b.brand_slug.replace(/-/g, ' ')).join(', ')}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* ── Section 2: Coverage Funnel + Category Distribution ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Coverage Funnel */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          className="lg:col-span-2"
        >
          <Card className="shadow-sm h-full">
            <CardHeader>
              <CardTitle className="font-display text-xl font-semibold">Coverage Funnel</CardTitle>
              <CardDescription>Product pipeline from discovery to verification</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={funnelWithPercent} layout="vertical" margin={{ left: 10, right: 50, top: 5, bottom: 5 }}>
                  <XAxis type="number" tick={{ fontSize: 11, fill: COLORS.inkMuted }} axisLine={false} tickLine={false} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fontSize: 12, fill: COLORS.ink, fontWeight: 500 }}
                    axisLine={false}
                    tickLine={false}
                    width={110}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(26,23,20,0.03)' }} />
                  <Bar
                    dataKey="value"
                    name="Products"
                    fill={COLORS.champagne}
                    radius={[0, 6, 6, 0]}
                    barSize={28}
                    label={{ position: 'right', fontSize: 11, fill: COLORS.inkMuted, fontWeight: 500 }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        {/* Category Distribution */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
        >
          <Card className="shadow-sm h-full">
            <CardHeader>
              <CardTitle className="font-display text-xl font-semibold">Categories</CardTitle>
              <CardDescription>Product category distribution</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center">
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={typeData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={90}
                      paddingAngle={2}
                      dataKey="value"
                      stroke="none"
                    >
                      {typeData.map((_, i) => (
                        <Cell key={i} fill={typeColors[i % typeColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: 'white',
                        border: '1px solid rgba(26,23,20,0.05)',
                        borderRadius: 12,
                        fontSize: 12,
                        boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-col gap-2 w-full mt-2">
                  {typeData.map((d, i) => (
                    <div key={d.name} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: typeColors[i % typeColors.length] }} />
                        <span className="text-ink-muted truncate">{d.name}</span>
                      </div>
                      <span className="font-medium text-ink tabular-nums ml-2">{d.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* ── Section 3: Seals + Quick Actions ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Top Quality Seals */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.45 }}
        >
          <Card className="shadow-sm h-full">
            <CardHeader>
              <CardTitle className="font-display text-xl font-semibold">Top Quality Seals</CardTitle>
              <CardDescription>Most common detected and inferred labels</CardDescription>
            </CardHeader>
            <CardContent>
              {sealDistributionData.length > 0 ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {sealDistributionData.slice(0, 5).map(s => (
                      <Badge key={s.key} variant="secondary" className="text-[10px]">
                        {s.name}
                      </Badge>
                    ))}
                  </div>
                  <ResponsiveContainer width="100%" height={Math.max(220, sealDistributionData.length * 30)}>
                    <BarChart data={sealDistributionData} layout="vertical" margin={{ left: 10, right: 40, top: 0, bottom: 0 }}>
                      <XAxis type="number" tick={{ fontSize: 11, fill: COLORS.inkMuted }} axisLine={false} tickLine={false} />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 11, fill: COLORS.ink, fontWeight: 500 }}
                        axisLine={false}
                        tickLine={false}
                        width={120}
                      />
                      <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(26,23,20,0.03)' }} />
                      <Bar
                        dataKey="count"
                        name="Products"
                        fill={COLORS.sage}
                        radius={[0, 6, 6, 0]}
                        barSize={22}
                        label={{ position: 'right', fontSize: 11, fill: COLORS.inkMuted, fontWeight: 500 }}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="flex items-center justify-center h-40 text-xs text-ink-muted">No seal data available</div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="flex flex-col gap-6"
        >
          <Card className="shadow-sm hover:shadow-md transition-shadow duration-300 flex-1">
            <CardContent className="pt-6 flex flex-col justify-between h-full">
              <div>
                <div className="w-12 h-12 rounded-xl bg-champagne/10 flex items-center justify-center mb-4 text-champagne-dark">
                  <PackageIcon />
                </div>
                <h3 className="font-display text-lg font-semibold text-ink">Browse Products</h3>
                <p className="text-sm text-ink-muted mt-1">
                  Explore all {stats.total.toLocaleString()} products. Search, filter, and review product details.
                </p>
              </div>
              <div className="mt-4">
                <Link to="/products">
                  <Button className="bg-champagne text-white hover:bg-champagne/90 w-full">
                    Browse Products
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>

          <Card className={cn(
            'shadow-sm hover:shadow-md transition-shadow duration-300 flex-1',
            pendingCount > 0 && 'ring-1 ring-coral/20'
          )}>
            <CardContent className="pt-6 flex flex-col justify-between h-full">
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-coral/10 flex items-center justify-center text-coral">
                    <AlertTriangleIcon />
                  </div>
                  {pendingCount > 0 && (
                    <Badge variant="destructive" className="text-xs">
                      {pendingCount} pending
                    </Badge>
                  )}
                </div>
                <h3 className="font-display text-lg font-semibold text-ink">Review Quarantine</h3>
                <p className="text-sm text-ink-muted mt-1">
                  {pendingCount > 0
                    ? `${pendingCount} product${pendingCount !== 1 ? 's' : ''} flagged for manual review.`
                    : 'No products pending review. All clear!'}
                </p>
              </div>
              <div className="mt-4">
                <Link to="/quarantine">
                  <Button className={cn(
                    'w-full',
                    pendingCount > 0
                      ? 'bg-coral text-white hover:bg-coral/90'
                      : 'bg-ink/10 text-ink hover:bg-ink/20'
                  )}>
                    Review Quarantine
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
