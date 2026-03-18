/**
 * Beat state store — receives data from WebSocket and interpolates between updates.
 */
import { wsClient } from '$lib/ws/client';

class BeatStore {
  bpm = $state(0);
  beatPhase = $state(0);
  barPhase = $state(0);
  isPlaying = $state(false);
  beatPos = $state(1);
  pitchPercent = $state<number | null>(null);
  deckNumber = $state<number | null>(null);
  deckName = $state<string | null>(null);
  wsConnected = $state(false);

  private lastUpdate = 0;
  private animFrame = 0;

  constructor() {
    // Listen for beat messages from WS
    wsClient.on('beat', (msg) => {
      this.bpm = (msg.bpm as number) || 0;
      this.beatPhase = (msg.beat_phase as number) || 0;
      this.barPhase = (msg.bar_phase as number) || 0;
      this.isPlaying = (msg.is_playing as boolean) || false;
      this.beatPos = (msg.beat_pos as number) || 1;
      this.pitchPercent = (msg.pitch_percent as number) ?? null;
      this.deckNumber = (msg.deck_number as number) ?? null;
      this.deckName = (msg.deck_name as string) ?? null;
      this.lastUpdate = performance.now();
    });

    // Track connection state
    this._pollConnection();
  }

  private _pollConnection(): void {
    const check = () => {
      this.wsConnected = wsClient.connected;
      requestAnimationFrame(check);
    };
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(check);
    }
  }

  /**
   * Start client-side phase interpolation between server updates.
   */
  startInterpolation(): void {
    const tick = () => {
      if (this.isPlaying && this.bpm > 0 && this.lastUpdate > 0) {
        const elapsed = (performance.now() - this.lastUpdate) / 1000;
        const beatsPerSec = this.bpm / 60;
        const phaseDelta = (elapsed * beatsPerSec) % 1;

        this.beatPhase = (this.beatPhase + phaseDelta) % 1;
        this.barPhase = (this.barPhase + phaseDelta / 4) % 1;
        this.lastUpdate = performance.now();
      }
      this.animFrame = requestAnimationFrame(tick);
    };
    if (typeof requestAnimationFrame !== 'undefined') {
      this.animFrame = requestAnimationFrame(tick);
    }
  }

  stopInterpolation(): void {
    if (this.animFrame) {
      cancelAnimationFrame(this.animFrame);
      this.animFrame = 0;
    }
  }
}

export const beatStore = new BeatStore();
