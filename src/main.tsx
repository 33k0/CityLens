import { SCREENS } from './cvm/screens'

/* #data -> the plain data viewer (React + Tailwind). Anything else -> the CityLens map UI.
   The map UI is loaded without Tailwind because its base styles would restyle the design's inline SVG icons. */
async function boot() {
  const root = document.getElementById('root')!
  if (location.hash.startsWith('#data')) {
    await import('./index.css')
    const [{ StrictMode, createElement }, { createRoot }, { default: App }] = await Promise.all([
      import('react'), import('react-dom/client'), import('./App.tsx'),
    ])
    createRoot(root).render(createElement(StrictMode, null, createElement(App)))
    return
  }
  const { mount } = await import('./cvm/cvm.js')
  const screen = new URLSearchParams(location.search).get('screen') ?? ''
  try {
    await mount(root, { ...(SCREENS[screen] ?? { scheme: 'voice', tab: 'chat' }) })
  } catch (e) {
    root.innerHTML = `<div style="font:14px system-ui;padding:32px;max-width:640px"><b>Could not load the map data.</b><br>${String(e)}<br><br>Run <code>npm run data</code> (or <code>npm run data:offline</code>) and reload. The raw data viewer is at <a href="#data">#data</a>.</div>`
    console.error(e)
  }
}
boot()
