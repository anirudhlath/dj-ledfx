# dj-ledfx web app: design assets

The design handoff lives in `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md`. Start there.

| File | What it is |
|---|---|
| `tokens.css` | Tailwind v4 `@theme` tokens, base styles, `tape`, `label-caps`, `num` utilities |
| `icons.ts` | The app's 65 icons (24 px grid, stroke 1.6) |
| `home.json` | Seed geometry: rooms, walls, windows, columns, furniture, anchors, sub-zones, 19 lights with shapes. Metres; x east, y south, z up. All positions are estimates until confirmed |
| `looks.json` | The 29 built-in looks: id, name, category, inputs, description, thumbnail motif |
| `reference/*.png` | Rendered artboards (desktop 1440 wide, phone 390 × 844) |
| `reference/*.html` | The same artboards as standalone pages; links between them work, thumbnails animate |

The 3D stage in the references is an SVG approximation. Build the real one to section 7 of the spec.
