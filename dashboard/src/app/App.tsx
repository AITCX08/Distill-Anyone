import { MissionControlPage } from "../features/mission-control/MissionControlPage";
import { useMissionControl } from "../features/mission-control/useMissionControl";
import { CreateJobPage } from "../features/create-job/CreateJobPage";
import { AppShell } from "./AppShell";

export function App() {
  const mission = useMissionControl();

  return (
    <AppShell>
      {mission
        ? <MissionControlPage
          snapshot={mission.snapshot}
          job={mission.job}
          traceEntries={mission.traceEntries}
          onJobUpdated={mission.updateJob}
        />
        : <section id="mission" aria-label="Mission Control"><p>Waiting for server snapshot...</p></section>}
      <CreateJobPage />
    </AppShell>
  );
}
