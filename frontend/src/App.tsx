import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import { AuthProvider } from './lib/auth'
import Login from './pages/Login'
import OpsLayout from './components/ops/OpsLayout'
import OpsDashboard from './pages/ops/OpsDashboard'
import OpsProducts from './pages/ops/OpsProducts'
import OpsProductDetail from './pages/ops/OpsProductDetail'
import OpsIngredients from './pages/ops/OpsIngredients'
import OpsSettings from './pages/ops/OpsSettings'
import BrandsDashboard from './pages/BrandsDashboard'
import BrandPage from './pages/BrandPage'
// ProductDetail is now handled by OpsProductDetail via redirect

function RedirectToProduct() {
  const { productId } = useParams();
  return <Navigate to={`/ops/products/${productId}`} replace />;
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <h1 className="text-4xl font-bold text-ink">404</h1>
      <p className="mt-2 text-ink-muted">Página não encontrada</p>
      <a href="/ops" className="mt-4 text-sm text-champagne-dark hover:underline">Voltar ao início</a>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/ops" element={<OpsLayout />}>
          <Route index element={<OpsDashboard />} />
          <Route path="products" element={<OpsProducts />} />
          <Route path="products/:id" element={<OpsProductDetail />} />
          <Route path="ingredients" element={<OpsIngredients />} />
          <Route path="settings" element={<OpsSettings />} />
          <Route path="brands" element={<BrandsDashboard />} />
          <Route path="brands/:slug" element={<BrandPage />} />
          <Route path="brands/:slug/products/:productId" element={<RedirectToProduct />} />
        </Route>

        {/* All redirects → unified interface */}
        <Route path="/" element={<Navigate to="/ops" replace />} />
        <Route path="/brands" element={<Navigate to="/ops/brands" replace />} />
        <Route path="/brands/:slug" element={<Navigate to="/ops/brands/:slug" replace />} />
        <Route path="/explorer" element={<Navigate to="/ops/products" replace />} />
        <Route path="/explorador" element={<Navigate to="/ops/products" replace />} />
        <Route path="/products" element={<Navigate to="/ops/products" replace />} />
        <Route path="/admin" element={<Navigate to="/ops" replace />} />
        <Route path="/admin/*" element={<Navigate to="/ops" replace />} />
        <Route path="/quarantine" element={<Navigate to="/ops" replace />} />
        <Route path="/review-queue" element={<Navigate to="/ops/products" replace />} />
        {/* Redirects for removed pages */}
        <Route path="/ops/explorer" element={<Navigate to="/ops/products" replace />} />
        <Route path="/ops/review" element={<Navigate to="/ops/products" replace />} />
        <Route path="/ops/inci" element={<Navigate to="/ops/products?verification_status=catalog_only" replace />} />

        {/* 404 catch-all */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
