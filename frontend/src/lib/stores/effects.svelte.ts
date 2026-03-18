/**
 * Effects store — manages active effect, parameters, and presets.
 */
import * as api from '$lib/api/client';
import type { EffectParamSchema, Preset } from '$lib/api/client';
import { wsClient } from '$lib/ws/client';

class EffectsStore {
  activeEffect = $state('');
  activeParams = $state<Record<string, unknown>>({});
  effectSchemas = $state<Record<string, Record<string, EffectParamSchema>>>({});
  presets = $state<Preset[]>([]);
  loading = $state(false);

  async init(): Promise<void> {
    this.loading = true;
    try {
      const [effects, active, presets] = await Promise.all([
        api.getEffects(),
        api.getActiveEffect(),
        api.getPresets(),
      ]);
      this.effectSchemas = effects;
      this.activeEffect = active.effect;
      this.activeParams = active.params;
      this.presets = presets;
    } catch (e) {
      console.error('Failed to initialize effects store:', e);
    } finally {
      this.loading = false;
    }
  }

  async switchEffect(name: string, params?: Record<string, unknown>): Promise<void> {
    try {
      const result = await api.setActiveEffect({ effect: name, params });
      this.activeEffect = result.effect;
      this.activeParams = result.params;
    } catch (e) {
      console.error('Failed to switch effect:', e);
    }
  }

  async updateParam(key: string, value: unknown): Promise<void> {
    try {
      const result = await api.setActiveEffect({ params: { [key]: value } });
      this.activeParams = result.params;
    } catch (e) {
      console.error('Failed to update param:', e);
    }
  }

  async loadPreset(name: string): Promise<void> {
    try {
      const result = await api.loadPreset(name);
      this.activeEffect = result.effect;
      this.activeParams = result.params;
    } catch (e) {
      console.error('Failed to load preset:', e);
    }
  }

  async savePreset(name: string): Promise<void> {
    try {
      await api.savePreset(name);
      this.presets = await api.getPresets();
    } catch (e) {
      console.error('Failed to save preset:', e);
    }
  }

  async deletePreset(name: string): Promise<void> {
    try {
      await api.deletePreset(name);
      this.presets = await api.getPresets();
    } catch (e) {
      console.error('Failed to delete preset:', e);
    }
  }
}

export const effectsStore = new EffectsStore();
