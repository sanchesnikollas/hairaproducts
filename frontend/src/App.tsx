import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import BrandsDashboard from './pages/BrandsDashboard'
import BrandDetail from './pages/BrandDetail'
import BrandPage from './pages/BrandPage'
import ProductDetail from './pages/ProductDetail'
import ProductBrowser from './pages/ProductBrowser'
import QuarantineReview from './pages/QuarantineReview'
import ReviewQueue from './pages/ReviewQueue'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Public */}
        <Route index element={<Home />} />
        <Route path="brands" element={<BrandsDashboard />} />
        <Route path="brands/:slug" element={<BrandPage />} />
        <Route path="brands/:slug/products/:productId" element={<ProductDetail />} />

        {/* Admin */}
        <Route path="admin" element={<Dashboard />} />
        <Route path="admin/products" element={<ProductBrowser />} />
        <Route path="admin/quarantine" element={<QuarantineReview />} />
        <Route path="admin/review-queue" element={<ReviewQueue />} />

        {/* Legacy redirects */}
        <Route path="products" element={<ProductBrowser />} />
        <Route path="quarantine" element={<QuarantineReview />} />
        <Route path="review-queue" element={<ReviewQueue />} />

        {/* Legacy brand detail */}
        <Route path="brand-detail/:slug" element={<BrandDetail />} />
      </Route>
    </Routes>
  )
}

export default App
