import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { routerBasename } from './app/router'
import { routes } from './app/routes'
import './styles/app.css'

const router = createBrowserRouter(routes, { basename: routerBasename(import.meta.env.BASE_URL) })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
