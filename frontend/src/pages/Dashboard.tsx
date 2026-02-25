import { useMemo } from 'react'
import { motion } from 'motion/react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
  AreaChart, Area,
  Legend,
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

// ── Animated Counter ──

function AnimatedNumber({ value, suffix = '', prefix = '' }: { value: number; suffix?: string; prefix?: string }) {
  return (
    <motion.span
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className="tabular-nums"
    >
      {prefix}{typeof value === 'number' && value % 1 !== 0 ? value.toFixed(1) : value.toLocaleString()}{suffix}
    </motion.span>
  )
}

// ── Stat Card ──

function StatCard({ label, value, suffix, prefix, accent, icon, delay = 0 }: {
  label: string
  value: number
  suffix?: string
  prefix?: string
  accent: 'sage' | 'champagne' | 'coral' | 'amber'
  icon: React.ReactNode
  delay?: number
}) {
  const accentMap = {
    sage: 'border-sage/20 bg-sage-bg/50',
    champagne: 'border-champagne/20 bg-champagne/5',
    coral: 'border-coral/20 bg-coral-bg/50',
    amber: 'border-amber/20 bg-amber-bg/50',
  }
  const iconBg = {
    sage: 'bg-sage/10 text-sage',
    champagne: 'bg-champagne/10 text-champagne-dark',
    coral: 'bg-coral/10 text-coral',
    amber: 'bg-amber/10 text-amber',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className={`rounded-2xl border ${accentMap[accent]} p-6 flex flex-col gap-3`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-[0.15em] font-medium text-ink-muted">{label}</span>
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${iconBg[accent]}`}>
          {icon}
        </div>
      </div>
      <span className="font-display text-4xl font-semibold text-ink tracking-tight leading-none">
        <AnimatedNumber value={value} suffix={suffix} prefix={prefix} />
      </span>
    </motion.div>
  )
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

// ── Pipeline Breakdown Label ──

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

// ── Main Dashboard ──

export default function Dashboard() {
  const { data: brands, loading: brandsLoading, error: brandsError } = useAPI(getBrands)
  const { data: products, loading: productsLoading, error: productsError } = useAPI(
    () => getProducts({ verified_only: false, per_page: 500 })
  )

  const loading = brandsLoading || productsLoading
  const error = brandsError || productsError

  // ── Computed Stats ──

  const stats = useMemo(() => {
    if (!brands) return null
    const totalExtracted = brands.reduce((s, b) => s + b.extracted_total, 0)
    const totalVerified = brands.reduce((s, b) => s + b.verified_inci_total, 0)
    const totalCatalog = brands.reduce((s, b) => s + b.catalog_only_total, 0)
    const totalQuarantined = brands.reduce((s, b) => s + b.quarantined_total, 0)
    const totalDiscovered = brands.reduce((s, b) => s + b.discovered_total, 0)
    const avgRate = totalExtracted > 0 ? (totalVerified / totalExtracted) * 100 : 0
    return { totalExtracted, totalVerified, totalCatalog, totalQuarantined, totalDiscovered, avgRate, brandCount: brands.length }
  }, [brands])

  // ── Brand Comparison Data ──

  const brandChartData = useMemo(() => {
    if (!brands) return []
    return brands
      .sort((a, b) => b.extracted_total - a.extracted_total)
      .map(b => ({
        name: b.brand_slug.charAt(0).toUpperCase() + b.brand_slug.slice(1),
        verified: b.verified_inci_total,
        catalog: b.catalog_only_total,
        quarantined: b.quarantined_total,
        rate: Math.round(b.verified_inci_rate * 100),
      }))
  }, [brands])

  // ── Pipeline Donut ──

  const pipelineData = useMemo(() => {
    if (!stats) return []
    return [
      { name: 'Verified INCI', value: stats.totalVerified, color: COLORS.sage },
      { name: 'Catalog Only', value: stats.totalCatalog, color: COLORS.champagne },
      { name: 'Quarantined', value: stats.totalQuarantined, color: COLORS.coral },
    ].filter(d => d.value > 0)
  }, [stats])

  // ── Verification Rate by Brand ──

  const rateData = useMemo(() => {
    if (!brands) return []
    return brands
      .sort((a, b) => b.verified_inci_rate - a.verified_inci_rate)
      .map(b => ({
        name: b.brand_slug.charAt(0).toUpperCase() + b.brand_slug.slice(1),
        rate: Math.round(b.verified_inci_rate * 100),
        fill: b.verified_inci_rate >= 0.7 ? COLORS.sage : b.verified_inci_rate >= 0.4 ? COLORS.champagne : COLORS.coral,
      }))
  }, [brands])

  // ── Product Type Distribution ──

  const typeData = useMemo(() => {
    if (!products) return []
    const counts: Record<string, number> = {}
    products.forEach(p => {
      const t = p.product_type_normalized || 'other'
      counts[t] = (counts[t] || 0) + 1
    })
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, value]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), value }))
  }, [products])

  const typeColors = [
    COLORS.sage, COLORS.champagne, COLORS.coral, COLORS.amber,
    '#8B9DC3', '#A6854A', '#9B8EC2', COLORS.inkFaint,
  ]

  // ── Discovery Funnel ──

  const funnelData = useMemo(() => {
    if (!brands) return []
    return brands.map(b => ({
      name: b.brand_slug.charAt(0).toUpperCase() + b.brand_slug.slice(1),
      discovered: b.discovered_total,
      extracted: b.extracted_total,
      verified: b.verified_inci_total,
    }))
  }, [brands])

  // ── Render ──

  if (loading) return <LoadingState message="Loading dashboard data..." />
  if (error) return <ErrorState message={error} />
  if (!stats || !brands) return null

  return (
    <div className="space-y-8 pb-12">

      {/* ── Page Title ── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="font-display text-4xl font-semibold text-ink tracking-tight">
          Dashboard
        </h1>
        <p className="text-ink-muted text-sm mt-1">
          Pipeline overview across {stats.brandCount} brands &middot; {stats.totalDiscovered.toLocaleString()} URLs discovered
        </p>
      </motion.div>

      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Products Extracted"
          value={stats.totalExtracted}
          accent="champagne"
          delay={0.05}
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 2h6l3 7H6L9 2z"/><rect x="4" y="9" width="16" height="13" rx="2"/></svg>}
        />
        <StatCard
          label="Verified INCI"
          value={stats.totalVerified}
          accent="sage"
          delay={0.1}
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>}
        />
        <StatCard
          label="Verification Rate"
          value={stats.avgRate}
          suffix="%"
          accent={stats.avgRate >= 50 ? 'sage' : 'amber'}
          delay={0.15}
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>}
        />
        <StatCard
          label="Quarantined"
          value={stats.totalQuarantined}
          accent="coral"
          delay={0.2}
          icon={<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 9v4M12 17h.01"/><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>}
        />
      </div>

      {/* ── Row 2: Brand Comparison + Pipeline Donut ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Brand Stacked Bar Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
          className="lg:col-span-2 bg-white rounded-2xl border border-ink/5 p-6"
        >
          <h2 className="font-display text-xl font-semibold text-ink mb-1">Product Breakdown</h2>
          <p className="text-xs text-ink-muted mb-5">Products by brand and verification status</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={brandChartData} layout="vertical" margin={{ left: 20, right: 20, top: 0, bottom: 0 }}>
              <XAxis type="number" tick={{ fontSize: 11, fill: COLORS.inkMuted }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: COLORS.ink, fontWeight: 500 }} axisLine={false} tickLine={false} width={90} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(26,23,20,0.03)' }} />
              <Legend
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: 11, paddingTop: 12 }}
              />
              <Bar dataKey="verified" name="Verified" stackId="a" fill={COLORS.sage} radius={[0, 0, 0, 0]} />
              <Bar dataKey="catalog" name="Catalog" stackId="a" fill={COLORS.champagne} />
              <Bar dataKey="quarantined" name="Quarantined" stackId="a" fill={COLORS.coral} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Pipeline Donut */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="bg-white rounded-2xl border border-ink/5 p-6 flex flex-col items-center"
        >
          <h2 className="font-display text-xl font-semibold text-ink mb-1 self-start">Pipeline Status</h2>
          <p className="text-xs text-ink-muted mb-4 self-start">Overall verification breakdown</p>
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
            {/* Center label */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="font-display text-3xl font-semibold text-ink leading-none">{stats.totalExtracted}</span>
              <span className="text-[10px] uppercase tracking-[0.15em] text-ink-muted mt-1">Products</span>
            </div>
          </div>
          {/* Legend */}
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
      </div>

      {/* ── Row 3: Verification Rate + Product Types ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Verification Rate Bars */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          className="bg-white rounded-2xl border border-ink/5 p-6"
        >
          <h2 className="font-display text-xl font-semibold text-ink mb-1">Verification Rate</h2>
          <p className="text-xs text-ink-muted mb-5">INCI verification rate per brand</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={rateData} layout="vertical" margin={{ left: 20, right: 20, top: 0, bottom: 0 }}>
              <XAxis
                type="number"
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: COLORS.inkMuted }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: COLORS.ink, fontWeight: 500 }} axisLine={false} tickLine={false} width={90} />
              <Tooltip
                formatter={(v?: number) => [`${v ?? 0}%`, 'Rate']}
                contentStyle={{
                  background: 'white',
                  border: '1px solid rgba(26,23,20,0.05)',
                  borderRadius: 12,
                  fontSize: 12,
                  boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
                }}
                cursor={{ fill: 'rgba(26,23,20,0.03)' }}
              />
              <Bar dataKey="rate" radius={[0, 6, 6, 0]} barSize={28}>
                {rateData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Product Types Donut */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="bg-white rounded-2xl border border-ink/5 p-6"
        >
          <h2 className="font-display text-xl font-semibold text-ink mb-1">Product Types</h2>
          <p className="text-xs text-ink-muted mb-5">Distribution of product categories</p>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width={180} height={180}>
              <PieChart>
                <Pie
                  data={typeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={80}
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
            <div className="flex flex-col gap-2 flex-1 min-w-0">
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

      {/* ── Row 4: Discovery Funnel ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.45 }}
        className="bg-white rounded-2xl border border-ink/5 p-6"
      >
        <h2 className="font-display text-xl font-semibold text-ink mb-1">Discovery Funnel</h2>
        <p className="text-xs text-ink-muted mb-5">From URL discovery to INCI verification</p>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={funnelData} margin={{ left: 20, right: 20, top: 10, bottom: 0 }}>
            <defs>
              <linearGradient id="gradDiscovered" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.champagne} stopOpacity={0.3} />
                <stop offset="100%" stopColor={COLORS.champagne} stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="gradExtracted" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.amber} stopOpacity={0.3} />
                <stop offset="100%" stopColor={COLORS.amber} stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="gradVerified" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.sage} stopOpacity={0.4} />
                <stop offset="100%" stopColor={COLORS.sage} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: COLORS.ink, fontWeight: 500 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: COLORS.inkMuted }} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltip />} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingTop: 12 }} />
            <Area type="monotone" dataKey="discovered" name="Discovered" stroke={COLORS.champagne} fill="url(#gradDiscovered)" strokeWidth={2} />
            <Area type="monotone" dataKey="extracted" name="Extracted" stroke={COLORS.amber} fill="url(#gradExtracted)" strokeWidth={2} />
            <Area type="monotone" dataKey="verified" name="Verified" stroke={COLORS.sage} fill="url(#gradVerified)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      {/* ── Row 5: Brand Detail Table ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="bg-white rounded-2xl border border-ink/5 overflow-hidden"
      >
        <div className="p-6 pb-0">
          <h2 className="font-display text-xl font-semibold text-ink mb-1">Brand Details</h2>
          <p className="text-xs text-ink-muted mb-4">Complete breakdown for each brand in the pipeline</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-y border-ink/5">
                {['Brand', 'Status', 'Discovered', 'Extracted', 'Verified', 'Catalog', 'Quarantined', 'Rate'].map(h => (
                  <th key={h} className="px-6 py-3 text-left text-[10px] uppercase tracking-[0.15em] font-semibold text-ink-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {brands?.sort((a, b) => b.extracted_total - a.extracted_total).map((b, i) => {
                const rate = Math.round(b.verified_inci_rate * 100)
                const rateColor = rate >= 70 ? 'text-sage' : rate >= 40 ? 'text-amber' : 'text-coral'
                const barColor = rate >= 70 ? 'bg-sage' : rate >= 40 ? 'bg-amber' : 'bg-coral'
                const barTrack = rate >= 70 ? 'bg-sage-light/40' : rate >= 40 ? 'bg-amber-light/40' : 'bg-coral-light/40'
                return (
                  <motion.tr
                    key={b.brand_slug}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.55 + i * 0.05 }}
                    className="border-b border-ink/[0.03] hover:bg-champagne/[0.03] transition-colors"
                  >
                    <td className="px-6 py-4">
                      <span className="font-medium text-ink text-sm capitalize">{b.brand_slug}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center rounded-full text-[10px] px-2.5 py-0.5 font-medium uppercase tracking-wide ${
                        b.status === 'done' ? 'bg-sage-bg text-sage' : 'bg-amber-bg text-amber'
                      }`}>{b.status || 'unknown'}</span>
                    </td>
                    <td className="px-6 py-4 text-sm tabular-nums text-ink-muted">{b.discovered_total.toLocaleString()}</td>
                    <td className="px-6 py-4 text-sm tabular-nums font-medium text-ink">{b.extracted_total}</td>
                    <td className="px-6 py-4 text-sm tabular-nums font-medium text-sage">{b.verified_inci_total}</td>
                    <td className="px-6 py-4 text-sm tabular-nums text-champagne-dark">{b.catalog_only_total}</td>
                    <td className="px-6 py-4 text-sm tabular-nums text-coral">{b.quarantined_total}</td>
                    <td className="px-6 py-4 w-40">
                      <div className="flex items-center gap-3">
                        <div className={`flex-1 h-1.5 rounded-full ${barTrack} overflow-hidden`}>
                          <div className={`h-full rounded-full ${barColor} progress-bar-animated`} style={{ width: `${rate}%` }} />
                        </div>
                        <span className={`text-xs font-semibold tabular-nums ${rateColor}`}>{rate}%</span>
                      </div>
                    </td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </motion.div>

    </div>
  )
}
