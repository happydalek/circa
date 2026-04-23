export function renderHome(container: HTMLElement): void {
  container.innerHTML = `
    <div class="page home-page">
      <div class="logo">&#9834;</div>
      <h1>Not Hitster</h1>
      <p>Scan the QR code on a card to play a mystery song.</p>
      <button class="btn btn-primary" onclick="window.location.hash='#/scan'">
        Scan Card
      </button>
    </div>
  `
}
