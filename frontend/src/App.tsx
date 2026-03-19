import { BrowserRouter, Routes, Route, NavLink } from "react-router"
import { Toaster } from "@/components/ui/sonner"
import { Separator } from "@/components/ui/separator"
import { useWsConnection } from "@/hooks/use-ws-connection"
import LivePage from "@/pages/live"
import DevicesPage from "@/pages/devices"
import ConfigPage from "@/pages/config"
import ScenePage from "@/pages/scene"

function NavBar({ connected }: { connected: boolean }) {
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    [
      "text-xs font-semibold tracking-widest uppercase px-3 py-1.5 rounded transition-colors",
      isActive
        ? "text-foreground bg-muted"
        : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
    ].join(" ")

  return (
    <header className="flex items-center gap-4 px-4 h-12 border-b border-border shrink-0">
      {/* Brand */}
      <span className="text-sm font-bold tracking-tight select-none text-foreground/90">
        DJ&nbsp;<span className="text-primary">LEDFX</span>
      </span>

      <Separator orientation="vertical" className="h-5" />

      {/* Navigation */}
      <nav className="flex items-center gap-1">
        <NavLink to="/" end className={navLinkClass}>
          Live
        </NavLink>
        <NavLink to="/scene" className={navLinkClass}>
          Scene
        </NavLink>
        <NavLink to="/devices" className={navLinkClass}>
          Devices
        </NavLink>
        <NavLink to="/config" className={navLinkClass}>
          Config
        </NavLink>
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Connection status */}
      <div className="flex items-center gap-2">
        <span
          className={[
            "size-2 rounded-full transition-colors",
            connected ? "bg-green-500" : "bg-red-500/70",
          ].join(" ")}
        />
        <span className="text-xs text-muted-foreground">
          {connected ? "Connected" : "Disconnected"}
        </span>
      </div>
    </header>
  )
}

export default function App() {
  const connected = useWsConnection()

  return (
    <BrowserRouter>
      <div className="dark flex flex-col h-screen bg-background text-foreground">
        <NavBar connected={connected} />
        <main className="flex-1 overflow-auto p-4">
          <Routes>
            <Route path="/" element={<LivePage />} />
            <Route path="/scene" element={<ScenePage />} />
            <Route path="/devices" element={<DevicesPage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Routes>
        </main>
        <Toaster />
      </div>
    </BrowserRouter>
  )
}
