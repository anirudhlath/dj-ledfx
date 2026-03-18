/**
 * Devices store — tracks device list, groups, and live frame data.
 */
import * as api from '$lib/api/client';
import type { Device, Group } from '$lib/api/client';
import { wsClient } from '$lib/ws/client';

interface FrameData {
  rgb: Uint8Array;
  seq: number;
}

class DevicesStore {
  devices = $state<Device[]>([]);
  groups = $state<Record<string, Group>>({});
  frameData = $state(new Map<string, FrameData>());
  loading = $state(false);

  constructor() {
    // Update device stats from WS
    wsClient.on('stats', (msg) => {
      const statsDevices = msg.devices as Array<{
        name: string;
        fps: number;
        latency_ms: number;
        frames_dropped: number;
        connected: boolean;
      }>;
      if (!statsDevices) return;

      // Merge stats into existing device list
      this.devices = this.devices.map((d) => {
        const stats = statsDevices.find((s) => s.name === d.name);
        if (stats) {
          return {
            ...d,
            send_fps: stats.fps,
            effective_latency_ms: stats.latency_ms,
            frames_dropped: stats.frames_dropped,
            connected: stats.connected,
          };
        }
        return d;
      });
    });

    // Handle binary frame data
    wsClient.onFrame((frame) => {
      const newMap = new Map(this.frameData);
      newMap.set(frame.deviceName, { rgb: frame.rgb, seq: frame.seq });
      this.frameData = newMap;
    });
  }

  async init(): Promise<void> {
    this.loading = true;
    try {
      const [devices, groups] = await Promise.all([
        api.getDevices(),
        api.getGroups(),
      ]);
      this.devices = devices;
      this.groups = groups;
    } catch (e) {
      console.error('Failed to initialize devices store:', e);
    } finally {
      this.loading = false;
    }
  }

  async discover(): Promise<string[]> {
    try {
      const result = await api.discoverDevices();
      this.devices = await api.getDevices();
      return result.discovered;
    } catch (e) {
      console.error('Failed to discover devices:', e);
      return [];
    }
  }

  async identify(name: string): Promise<void> {
    await api.identifyDevice(name);
  }

  async createGroup(name: string, color: string): Promise<void> {
    await api.createGroup(name, color);
    this.groups = await api.getGroups();
  }

  async deleteGroup(name: string): Promise<void> {
    await api.deleteGroup(name);
    this.groups = await api.getGroups();
  }

  async assignGroup(deviceName: string, groupName: string): Promise<void> {
    await api.assignDeviceGroup(deviceName, groupName);
    this.devices = await api.getDevices();
  }
}

export const devicesStore = new DevicesStore();
