import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const root = createRoot(document.getElementById('root'))

// Dev-only preview screens (?preview=document, ?preview=errors). import.meta.env.DEV is a build-time
// constant, so in a production build this whole branch - and the dynamic import in it - is removed.
const preview = import.meta.env.DEV ? new URLSearchParams(window.location.search).get('preview') : null

if (import.meta.env.DEV && (preview === 'document' || preview === 'errors')) {
  import('./dev/Preview.jsx').then(({ default: Preview }) => {
    root.render(
      <StrictMode>
        <Preview mode={preview} />
      </StrictMode>,
    )
  })
} else {
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
