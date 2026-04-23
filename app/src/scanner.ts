import { Html5QrcodeScanner, Html5QrcodeScanType } from 'html5-qrcode'

export function renderScanner(container: HTMLElement): () => void {
  container.innerHTML = `
    <div class="page scanner-page">
      <button class="btn-back" onclick="window.location.hash='#/'">&#8592; Back</button>
      <p class="hint">Point the camera at a card's QR code</p>
      <div id="qr-reader"></div>
    </div>
  `

  const scanner = new Html5QrcodeScanner(
    'qr-reader',
    {
      fps: 10,
      qrbox: { width: 240, height: 240 },
      rememberLastUsedCamera: true,
      supportedScanTypes: [Html5QrcodeScanType.SCAN_TYPE_CAMERA],
    },
    false,
  )

  scanner.render(
    (decodedText: string) => {
      try {
        const url = new URL(decodedText)
        const hashPart = url.hash  // e.g. '#/play?v=<id>'
        const q = hashPart.indexOf('?')
        const params = new URLSearchParams(q >= 0 ? hashPart.slice(q + 1) : '')
        const v = params.get('v')
        if (v) {
          scanner.clear().catch(() => undefined)
          window.location.hash = `#/play?v=${encodeURIComponent(v)}`
        }
      } catch {
        // Not a valid URL — ignore and keep scanning
      }
    },
    (_errorMessage: string) => {
      // Transient decode failures are normal; ignore
    },
  )

  return () => {
    scanner.clear().catch(() => undefined)
  }
}
