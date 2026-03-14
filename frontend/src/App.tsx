import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import BrandsDashboard from './pages/BrandsDashboard'
import BrandDetail from './pages/BrandDetail'
import ProductBrowser from './pages/ProductBrowser'
import QuarantineReview from './pages/QuarantineReview'
import ReviewQueue from './pages/ReviewQueue'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="brands" element={<BrandsDashboard />} />
        <Route path="brands/:slug" element={<BrandDetail />} />
        <Route path="products" element={<ProductBrowser />} />
        <Route path="quarantine" element={<QuarantineReview />} />
        <Route path="review-queue" element={<ReviewQueue />} />
      </Route>
    </Routes>
  )
}

export default App
