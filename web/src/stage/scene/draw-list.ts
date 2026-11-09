// The canvas's layers draw on the stage's one cadence (cadence.ts): StageScene asks each in turn to
// write what's new into its meshes, and renders once in that animation frame if any did. Two layers
// each on a cadence of their own would render the canvas twice.
/** Writes what's new into a layer's meshes; whether it wrote anything. */
export type Drawer = () => boolean

export class DrawList {
  private readonly drawers = new Set<Drawer>()

  /** Adds `drawer`; returns what takes it out. */
  add(drawer: Drawer): () => void {
    this.drawers.add(drawer)
    return () => void this.drawers.delete(drawer)
  }

  /** Every layer draws; whether any wrote something, so the canvas has something new to show. */
  draw(): boolean {
    let changed = false
    for (const drawer of this.drawers) changed = drawer() || changed
    return changed
  }
}
