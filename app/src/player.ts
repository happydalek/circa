declare global {
  interface Window {
    YT: {
      Player: new (elementId: string, opts: YTPlayerOptions) => YTPlayer
      PlayerState: { PLAYING: number; PAUSED: number; ENDED: number }
    }
    onYouTubeIframeAPIReady: () => void
  }
}

interface YTPlayerOptions {
  videoId: string
  playerVars: Record<string, number>
  events: {
    onStateChange: (e: { data: number }) => void
  }
}

interface YTPlayer {
  playVideo(): void
  pauseVideo(): void
  getPlayerState(): number
}

export function renderPlayer(container: HTMLElement, videoId: string): void {
  if (!videoId) {
    container.innerHTML = `
      <div class="page">
        <p>No video ID found. <a href="#/">Go home</a></p>
      </div>
    `
    return
  }

  container.innerHTML = `
    <div class="page player-page">
      <button class="btn-back" onclick="window.location.hash='#/'">&#8592; Back</button>
      <div class="player-wrap">
        <div id="yt-player"></div>
        <div class="cover" id="cover">
          <div class="cover-content">
            <div class="music-note">&#9834;</div>
            <p class="cover-hint">Guess the song!</p>
          </div>
        </div>
      </div>
      <div class="controls">
        <button class="btn btn-play" id="btn-play">&#9654; Play</button>
        <button class="btn btn-reveal" id="btn-reveal">Reveal</button>
      </div>
    </div>
  `

  let ytPlayer: YTPlayer | null = null
  let isPlaying = false

  const btnPlay = document.getElementById('btn-play') as HTMLButtonElement
  const btnReveal = document.getElementById('btn-reveal') as HTMLButtonElement

  function initPlayer(): void {
    ytPlayer = new window.YT.Player('yt-player', {
      videoId,
      playerVars: {
        controls: 0,
        modestbranding: 1,
        rel: 0,
        showinfo: 0,
        iv_load_policy: 3,
        fs: 0,
        disablekb: 1,
        playsinline: 1,
      },
      events: {
        onStateChange: (e: { data: number }) => {
          isPlaying = e.data === window.YT.PlayerState.PLAYING
          btnPlay.innerHTML = isPlaying ? '&#9646;&#9646; Pause' : '&#9654; Play'
        },
      },
    })
  }

  btnPlay.addEventListener('click', () => {
    const p = ytPlayer
    if (!p) return
    isPlaying ? p.pauseVideo() : p.playVideo()
  })

  btnReveal.addEventListener('click', () => {
    document.getElementById('cover')!.classList.add('revealed')
    btnReveal.disabled = true
    btnReveal.textContent = 'Revealed'
  })

  if (window.YT?.Player) {
    initPlayer()
  } else {
    window.onYouTubeIframeAPIReady = initPlayer
    if (!document.querySelector('script[src*="youtube.com/iframe_api"]')) {
      const script = document.createElement('script')
      script.src = 'https://www.youtube.com/iframe_api'
      document.head.appendChild(script)
    }
  }
}
