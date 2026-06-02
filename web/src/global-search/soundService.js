class SoundService {
  ctx = null
  enabled = true
  assetCache = new Map()
  radarAudio = null

  playAsset(path, volume = 0.45, options = {}) {
    if (!this.enabled || typeof Audio === 'undefined') return false
    try {
      const cached = this.assetCache.get(path)
      const audio = cached ? cached.cloneNode() : new Audio(path)
      if (!cached) {
        const preloadAudio = new Audio(path)
        preloadAudio.preload = 'auto'
        this.assetCache.set(path, preloadAudio)
      }
      audio.volume = volume
      audio.loop = Boolean(options.loop)
      audio.currentTime = 0
      const playPromise = audio.play()
      if (playPromise?.catch) playPromise.catch(() => {})
      if (options.retain) return audio
      return true
    } catch {
      return false
    }
  }

  initCtx() {
    if (!this.enabled || typeof window === 'undefined') return
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!AudioCtx) return
    if (!this.ctx) this.ctx = new AudioCtx()
    if (this.ctx.state === 'suspended') this.ctx.resume()
  }

  setEnabled(val) {
    this.enabled = val
    if (!val) {
      this.stopRadarLoop()
      if (this.ctx) this.ctx.suspend()
    }
  }

  playClick() {
    if (!this.enabled) return
    if (this.playAsset('/sounds/re_menu_2.mp3', 0.5)) return
    this.initCtx()
    if (!this.ctx) return
    const now = this.ctx.currentTime
    const tick = this.ctx.createOscillator()
    const tickGain = this.ctx.createGain()
    tick.type = 'triangle'
    tick.frequency.setValueAtTime(2200, now)
    tick.frequency.exponentialRampToValueAtTime(1000, now + 0.02)
    tickGain.gain.setValueAtTime(0.05, now)
    tickGain.gain.exponentialRampToValueAtTime(0.001, now + 0.02)
    tick.connect(tickGain)
    tickGain.connect(this.ctx.destination)
    tick.start()
    tick.stop(now + 0.02)

    const thud = this.ctx.createOscillator()
    const thudGain = this.ctx.createGain()
    thud.type = 'triangle'
    thud.frequency.setValueAtTime(180, now)
    thud.frequency.exponentialRampToValueAtTime(60, now + 0.1)
    thudGain.gain.setValueAtTime(0.15, now)
    thudGain.gain.exponentialRampToValueAtTime(0.001, now + 0.1)
    thud.connect(thudGain)
    thudGain.connect(this.ctx.destination)
    thud.start()
    thud.stop(now + 0.1)
  }

  playCancel() {
    if (!this.enabled) return
    if (this.playAsset('/sounds/resident_evil_cancel.mp3', 0.55)) return
    this.playAction()
  }

  playAction() {
    if (!this.enabled) return
    if (this.playAsset('/sounds/resident_evil_3_menu.mp3', 0.5)) return
    this.initCtx()
    if (!this.ctx) return
    const now = this.ctx.currentTime
    const osc = this.ctx.createOscillator()
    const gain = this.ctx.createGain()
    const filter = this.ctx.createBiquadFilter()
    osc.type = 'sawtooth'
    osc.frequency.setValueAtTime(120, now)
    osc.frequency.exponentialRampToValueAtTime(40, now + 0.5)
    filter.type = 'lowpass'
    filter.frequency.setValueAtTime(3000, now)
    filter.Q.setValueAtTime(20, now)
    filter.frequency.exponentialRampToValueAtTime(200, now + 0.5)
    gain.gain.setValueAtTime(0.08, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5)
    osc.connect(filter)
    filter.connect(gain)
    gain.connect(this.ctx.destination)
    osc.start()
    osc.stop(now + 0.5)
  }

  playOpen() {
    this.playAction()
  }

  playBeep(freq = 440, duration = 0.1) {
    if (!this.enabled) return
    this.initCtx()
    if (!this.ctx) return
    const now = this.ctx.currentTime
    const osc = this.ctx.createOscillator()
    const gain = this.ctx.createGain()
    osc.type = 'square'
    osc.frequency.setValueAtTime(freq, now)
    gain.gain.setValueAtTime(0.03, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration)
    osc.connect(gain)
    gain.connect(this.ctx.destination)
    osc.start()
    osc.stop(now + duration)
  }

  playScan() {
    this.startRadarLoop()
  }

  playSuccess() {
    if (!this.enabled) return
    this.stopRadarLoop()
    if (this.playAsset('/sounds/choose.mp3', 0.6)) return
    this.initCtx()
    if (!this.ctx) return
    const now = this.ctx.currentTime
    const notes = [523.25, 659.25, 783.99, 1046.50] // C5, E5, G5, C6
    notes.forEach((freq, idx) => {
      const osc = this.ctx.createOscillator()
      const gain = this.ctx.createGain()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(freq, now + idx * 0.08)
      gain.gain.setValueAtTime(0.0, now + idx * 0.08)
      gain.gain.linearRampToValueAtTime(0.06, now + idx * 0.08 + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.3)
      osc.connect(gain)
      gain.connect(this.ctx.destination)
      osc.start(now + idx * 0.08)
      osc.stop(now + idx * 0.08 + 0.3)
    })
  }

  playError() {
    if (!this.enabled) return
    this.stopRadarLoop()
    this.initCtx()
    if (!this.ctx) return
    const now = this.ctx.currentTime
    const osc1 = this.ctx.createOscillator()
    const osc2 = this.ctx.createOscillator()
    const gain = this.ctx.createGain()
    osc1.type = 'square'
    osc1.frequency.setValueAtTime(110, now)
    osc2.type = 'square'
    osc2.frequency.setValueAtTime(115, now)
    gain.gain.setValueAtTime(0.1, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3)
    osc1.connect(gain)
    osc2.connect(gain)
    gain.connect(this.ctx.destination)
    osc1.start()
    osc2.start()
    osc1.stop(now + 0.3)
    osc2.stop(now + 0.3)
  }

  playRadarBeep() {
    if (!this.enabled) return
    if (this.playAsset('/sounds/radar_sms.mp3', 0.22)) return
    this.initCtx()
    if (!this.ctx) return
    const now = this.ctx.currentTime
    const osc = this.ctx.createOscillator()
    const gain = this.ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(800, now)
    osc.frequency.exponentialRampToValueAtTime(1200, now + 0.05)
    gain.gain.setValueAtTime(0.02, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1)
    osc.connect(gain)
    gain.connect(this.ctx.destination)
    osc.start()
    osc.stop(now + 0.1)
  }

  startRadarLoop() {
    if (!this.enabled || this.radarAudio) return
    const audio = this.playAsset('/sounds/radar_sms.mp3', 0.22, { loop: true, retain: true })
    if (audio && typeof audio !== 'boolean') {
      this.radarAudio = audio
    }
  }

  stopRadarLoop() {
    if (!this.radarAudio) return
    try {
      this.radarAudio.pause()
      this.radarAudio.currentTime = 0
    } catch {
      // ignore audio cleanup failures
    }
    this.radarAudio = null
  }
}

export const soundService = new SoundService()
