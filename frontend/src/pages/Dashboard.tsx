import { useMemo } from 'react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { useAPI } from '../hooks/useAPI'
import { getBrands, getProducts } from '../lib/api'
import LoadingState, { ErrorState } from '../components/LoadingState'

// ── Color Tokens ──

const COLORS = {
  sage: '#7A9E7E',
  sageBg: '#F0F7F1',
  champagne: '#C9A96E',
  champagneBg: '#FDF8EF',
  coral: '#C27C6B',
  coralBg: '#FDF5F2',
  amber: '#C9A040',
  amberBg: '#FFFBF0',
  ink: '#1A1714',
  inkMuted: '#7A7068',
  inkFaint: '#B8AFA6',
  cream: '#FAF7F2',
  white: '#FFFFFF',
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

// ── Pie Label ──

function PieLabel({ cx, cy, midAngle, innerRadius, outerRadius, value, percent }: {
  cx?: number; cy?: number; midAngle?: number; innerRadius?: number; outerRadius?: number;
  name?: string; value?: number; percent?: number
}) {
  if (!cx || !cy || !midAngle || !innerRadius || !outerRadius || !percent || percent < 0.05) return null
  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} textAnchor="middle" dominantBaseline="central" className="text-[11px] font-medium fill-white">
      {value}
    </text>
  )
}

// ── Status Legend Card ──

function StatusLegendCard({ color, icon, label, count, description, delay }: {
  color: string
  icon: React.ReactNode
  label: string
  count: number
  description: string
  delay: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="bg-white rounded-2xl border border-ink/5 p-5 space-y-3"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: color + '18' }}>
            <span style={{ color }}>{icon}</span>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.12em] font-semibold text-ink-muted">{label}</p>
            <p className="font-display text-2xl font-semibold text-ink leading-none mt-0.5 tabular-nums">{count.toLocaleString()}</p>
          </div>
        </div>
      </div>
      <p className="text-xs text-ink-muted leading-relaxed">{description}</p>
    </motion.div>
  )
}

// ── Main Dashboard ──

export default function Dashboard() {
  const { data: brands, loading: brandsLoading, error: brandsError } = useAPI(getBrands)
  const { data: productsResponse, loading: productsLoading, error: productsError } = useAPI(
    () => getProducts({ verified_only: false, per_page: 1000 })
  )
  const products = productsResponse?.items ?? null

  const loading = brandsLoading || productsLoading
  const error = brandsError || productsError

  // Use the first (and currently only) brand — Amend
  const brand = brands?.[0]

  // ── Computed Stats ──

  const stats = useMemo(() => {
    if (!brand) return null
    const rate = brand.extracted_total > 0 ? (brand.verified_inci_total / brand.extracted_total) * 100 : 0
    return {
      extracted: brand.extracted_total,
      verified: brand.verified_inci_total,
      catalog: brand.catalog_only_total,
      quarantined: brand.quarantined_total,
      rate,
    }
  }, [brand])

  // ── Pipeline Donut ──

  const pipelineData = useMemo(() => {
    if (!stats) return []
    return [
      { name: 'Verified INCI', value: stats.verified, color: COLORS.sage },
      { name: 'Catalog Only', value: stats.catalog, color: COLORS.champagne },
      { name: 'Quarantined', value: stats.quarantined, color: COLORS.coral },
    ].filter(d => d.value > 0)
  }, [stats])

  // ── Product Category Distribution ──

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

  const typeData = useMemo(() => {
    if (!products) return []
    const counts: Record<string, number> = {}
    products.forEach(p => {
      const t = p.product_category || 'Other'
      counts[t] = (counts[t] || 0) + 1
    })
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, value]) => ({ name: CATEGORY_LABELS[name] || name.charAt(0).toUpperCase() + name.slice(1), value }))
  }, [products])

  const typeColors = [
    COLORS.sage, COLORS.champagne, COLORS.coral, COLORS.amber,
    '#8B9DC3', '#A6854A', '#9B8EC2', COLORS.inkFaint, '#7CBDC4', '#C47C9B',
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
      .map(([key, count]) => ({
        name: SEAL_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        count,
      }))
  }, [products])

  // ── Labeled Products Count ──

  const labeledCount = useMemo(() => {
    if (!products) return 0
    return products.filter(p =>
      p.product_labels &&
      ((p.product_labels.detected && p.product_labels.detected.length > 0) ||
       (p.product_labels.inferred && p.product_labels.inferred.length > 0))
    ).length
  }, [products])

  // ── Render ──

  if (loading) return <LoadingState message="Loading dashboard data..." />
  if (error) return <ErrorState message={error} />
  if (!stats || !brand) return null

  const brandName = brand.brand_slug.charAt(0).toUpperCase() + brand.brand_slug.slice(1)

  return (
    <div className="space-y-8 pb-12">

      {/* ── Page Title ── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center gap-3">
          <h1 className="font-display text-4xl font-semibold text-ink tracking-tight">
            {brandName}
          </h1>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-champagne/10 text-champagne-dark border border-champagne/15">
            <span className="w-1.5 h-1.5 rounded-full bg-champagne" />
            Focus Brand
          </span>
        </div>
        <p className="text-ink-muted text-sm mt-1.5">
          {stats.extracted.toLocaleString()} products extracted &middot; {labeledCount.toLocaleString()} with quality seals &middot; {Math.round(stats.rate)}% INCI verification rate
        </p>
      </motion.div>

      {/* ── Status Guide ── */}
      <div>
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="text-[11px] uppercase tracking-[0.15em] font-semibold text-ink-muted mb-3"
        >
          Pipeline Status Guide
        </motion.h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatusLegendCard
            color={COLORS.sage}
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>}
            label="Verified INCI"
            count={stats.verified}
            description="Product with a complete, validated INCI ingredient list extracted from the source page. Ready for analysis and seal detection."
            delay={0.15}
          />
          <StatusLegendCard
            color={COLORS.champagne}
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 12h6M12 9v6"/></svg>}
            label="Catalog Only"
            count={stats.catalog}
            description="Product identified and cataloged but without a validated ingredient list. Common for hair dyes, peroxides, and kits. Can be manually completed in the product editor."
            delay={0.2}
          />
          <StatusLegendCard
            color={COLORS.coral}
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v4M12 17h.01"/><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>}
            label="Quarantined"
            count={stats.quarantined}
            description="Product with suspicious or incomplete data flagged for manual review. Check the Quarantine page to review and approve these."
            delay={0.25}
          />
          <StatusLegendCard
            color={COLORS.amber}
            icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 2h6l3 7H6L9 2z"/><rect x="4" y="9" width="16" height="13" rx="2"/></svg>}
            label="Total Extracted"
            count={stats.extracted}
            description="Total products successfully scraped from the brand's website. Includes all verification statuses. This is the complete product catalog."
            delay={0.3}
          />
        </div>
      </div>

      {/* ── Row 1: Pipeline Donut + Product Types ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Pipeline Donut */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          className="bg-white rounded-2xl border border-ink/5 p-6 flex flex-col items-center"
        >
          <h2 className="font-display text-xl font-semibold text-ink mb-1 self-start">Verification Breakdown</h2>
          <p className="text-xs text-ink-muted mb-4 self-start">How products are classified after extraction</p>
          <div className="relative">
            <ResponsiveContainer width={220} height={220}>
              <PieChart>
                <Pie
                  data={pipelineData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  labelLine={false}
                  label={PieLabel}
                  stroke="none"
                >
                  {pipelineData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value?: number, name?: string) => [value ?? 0, name ?? '']}
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
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="font-display text-3xl font-semibold text-ink leading-none">{Math.round(stats.rate)}%</span>
              <span className="text-[10px] uppercase tracking-[0.15em] text-ink-muted mt-1">INCI Rate</span>
            </div>
          </div>
          <div className="flex flex-col gap-2 mt-4 w-full">
            {pipelineData.map(d => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                  <span className="text-ink-muted">{d.name}</span>
                </div>
                <span className="font-medium text-ink tabular-nums">{d.value}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Product Types */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="lg:col-span-2 bg-white rounded-2xl border border-ink/5 p-6"
        >
          <h2 className="font-display text-xl font-semibold text-ink mb-1">Product Categories</h2>
          <p className="text-xs text-ink-muted mb-5">Distribution of product categories in the catalog</p>
          <div className="flex items-center gap-8">
            <ResponsiveContainer width={200} height={200}>
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
            <div className="flex flex-col gap-2.5 flex-1 min-w-0">
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
        </motion.div>
      </div>

      {/* ── Row 2: Seal Distribution ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.45 }}
        className="bg-white rounded-2xl border border-ink/5 p-6"
      >
        <h2 className="font-display text-xl font-semibold text-ink mb-1">Quality Seals</h2>
        <p className="text-xs text-ink-muted mb-5">
          Seals detected from product text and inferred from INCI ingredient analysis.
          {' '}{labeledCount} of {stats.extracted} products have at least one quality seal.
        </p>
        {sealDistributionData.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(280, sealDistributionData.length * 36)}>
            <BarChart data={sealDistributionData} layout="vertical" margin={{ left: 20, right: 40, top: 0, bottom: 0 }}>
              <XAxis type="number" tick={{ fontSize: 11, fill: COLORS.inkMuted }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: COLORS.ink, fontWeight: 500 }} axisLine={false} tickLine={false} width={130} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(26,23,20,0.03)' }} />
              <Bar dataKey="count" name="Products" fill={COLORS.sage} radius={[0, 6, 6, 0]} barSize={24} label={{ position: 'right', fontSize: 11, fill: COLORS.inkMuted, fontWeight: 500 }} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-40 text-xs text-ink-muted">No seal data available</div>
        )}
      </motion.div>

      {/* ── Quick Actions ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="grid grid-cols-1 sm:grid-cols-2 gap-4"
      >
        <Link
          to="/products"
          className="group bg-white rounded-2xl border border-ink/5 p-6 hover:border-champagne/20 hover:shadow-md transition-all"
        >
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-champagne/10 flex items-center justify-center text-champagne-dark group-hover:bg-champagne/20 transition-colors">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M9 2h6l3 7H6L9 2z" />
                <rect x="4" y="9" width="16" height="13" rx="2" />
                <path d="M10 13h4" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink group-hover:text-champagne-dark transition-colors">Browse & Edit Products</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Review all {stats.extracted} products. Click any product to edit fields, add INCI ingredients, and validate data.
              </p>
            </div>
          </div>
        </Link>

        {stats.quarantined > 0 && (
          <Link
            to="/quarantine"
            className="group bg-white rounded-2xl border border-ink/5 p-6 hover:border-coral/20 hover:shadow-md transition-all"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-coral/10 flex items-center justify-center text-coral group-hover:bg-coral/20 transition-colors">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 9v4M12 17h.01" />
                  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-ink group-hover:text-coral transition-colors">Review Quarantine</h3>
                <p className="text-xs text-ink-muted mt-0.5">
                  {stats.quarantined} product{stats.quarantined !== 1 ? 's' : ''} flagged for review. Approve or investigate suspicious data.
                </p>
              </div>
            </div>
          </Link>
        )}
      </motion.div>
    </div>
  )
}
