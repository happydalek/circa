import { registerSW } from 'virtual:pwa-register'
import './style.css'
import { renderHome } from './home'
import { renderScanner } from './scanner'
import { renderPlayer } from './player'

registerSW({ immediate: true })

let cleanup: (() => void) | null = null

function route(): void {
  if (cleanup) {
    cleanup()
    cleanup = null
  }

  const hash = window.location.hash || '#/'
  const app = document.getElementById('app')!

  if (hash.startsWith('#/play')) {
    const q = hash.indexOf('?')
    const params = new URLSearchParams(q >= 0 ? hash.slice(q + 1) : '')
    renderPlayer(app, params.get('v') ?? '')
  } else if (hash === '#/scan') {
    cleanup = renderScanner(app)
  } else {
    renderHome(app)
  }
}

window.addEventListener('hashchange', route)
route()
