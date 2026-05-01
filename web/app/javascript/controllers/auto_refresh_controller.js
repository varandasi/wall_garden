import { Controller } from '@hotwired/stimulus'

// Polls the current page on `intervalValue` and morphs the inner element
// matching `targetIdValue` with the response's same-id element.
//
// Used by the dashboard so live readings update without a full page reload.
export default class extends Controller {
  static values = {
    interval: { type: Number, default: 5000 },
    targetId: String,
  }

  connect () {
    this.timer = setInterval(() => this.refresh(), this.intervalValue)
  }

  disconnect () {
    if (this.timer) clearInterval(this.timer)
  }

  async refresh () {
    if (document.hidden) return
    try {
      const res = await fetch(window.location.pathname, {
        headers: { Accept: 'text/html' },
        credentials: 'same-origin',
      })
      if (!res.ok) return
      const html = await res.text()
      const parser = new DOMParser()
      const doc = parser.parseFromString(html, 'text/html')
      const fresh = doc.getElementById(this.targetIdValue)
      const here = document.getElementById(this.targetIdValue)
      if (fresh && here) here.replaceWith(fresh)
    } catch {
      /* swallow — next tick will retry */
    }
  }
}
