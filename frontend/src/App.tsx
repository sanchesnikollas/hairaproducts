import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import BrandsDashboard from './pages/BrandsDashboard'
import ProductBrowser from './pages/ProductBrowser'
import QuarantineReview from './pages/QuarantineReview'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="brands" element={<BrandsDashboard />} />
        <Route path="products" element={<ProductBrowser />} />
        <Route path="quarantine" element={<QuarantineReview />} />
      </Route>
    </Routes>
  )
}

export default App
