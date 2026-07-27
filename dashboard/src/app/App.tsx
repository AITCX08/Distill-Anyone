import { MissionControlPage } from "../features/mission-control/MissionControlPage";
import { useMissionControl } from "../features/mission-control/useMissionControl";
import { AppShell } from "./AppShell";

export function App() {
  const snapshot = useMissionControl();

  return (
    <AppShell>
      {snapshot
        ? <MissionControlPage snapshot={snapshot} />
        : <section id="mission" aria-label="Mission Control"><p>Waiting for server snapshot...</p></section>}
    </AppShell>
  );
}
