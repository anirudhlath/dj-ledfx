import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/app.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <h1 className="p-6 font-serif text-display-lg">dj-ledfx</h1>
  </StrictMode>,
)
