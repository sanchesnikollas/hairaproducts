import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import BrandsDashboard from './pages/BrandsDashboard'
import BrandPage from './pages/BrandPage'
import ProductDetail from './pages/ProductDetail'
import ProductBrowser from './pages/ProductBrowser'
import { AuthProvider } from './lib/auth'
import Login from './pages/Login'
import OpsLayout from './components/ops/OpsLayout'
import OpsDashboard from './pages/ops/OpsDashboard'
import OpsProducts from './pages/ops/OpsProducts'
import OpsProductDetail from './pages/ops/OpsProductDetail'
import OpsReview from './pages/ops/OpsReview'
import OpsIngredients from './pages/ops/OpsIngredients'
import OpsSettings from './pages/ops/OpsSettings'

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/ops" element={<OpsLayout />}>
          <Route index element={<OpsDashboard />} />
          <Route path="products" element={<OpsProducts />} />
          <Route path="products/:id" element={<OpsProductDetail />} />
          <Route path="review" element={<OpsReview />} />
          <Route path="ingredients" element={<OpsIngredients />} />
          <Route path="settings" element={<OpsSettings />} />
        </Route>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="brands" element={<BrandsDashboard />} />
          <Route path="brands/:slug" element={<BrandPage />} />
          <Route path="brands/:slug/products/:productId" element={<ProductDetail />} />
          <Route path="explorer" element={<ProductBrowser />} />

          {/* Redirects from old routes */}
          <Route path="admin" element={<Navigate to="/" replace />} />
          <Route path="admin/products" element={<Navigate to="/explorer" replace />} />
          <Route path="admin/quarantine" element={<Navigate to="/" replace />} />
          <Route path="admin/review-queue" element={<Navigate to="/" replace />} />
          <Route path="products" element={<Navigate to="/explorer" replace />} />
          <Route path="quarantine" element={<Navigate to="/" replace />} />
          <Route path="review-queue" element={<Navigate to="/" replace />} />
          <Route path="brand-detail/:slug" element={<Navigate to="/brands/:slug" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}

export default App
