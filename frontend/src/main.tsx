import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// No StrictMode: it double-invokes effects in dev, which would open the scan
// EventSource twice.
createRoot(document.getElementById('root')!).render(<App />)
