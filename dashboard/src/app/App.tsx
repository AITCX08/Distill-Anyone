import { MissionControlPage } from "../features/mission-control/MissionControlPage";
import { useMissionControl } from "../features/mission-control/useMissionControl";
import { CreateJobPage } from "../features/create-job/CreateJobPage";
import { PlatformsPage } from "../features/platforms/PlatformsPage";
import { JobHistoryPage } from "../features/job-history/JobHistoryPage";
import { ArtifactsPage } from "../features/artifacts/ArtifactsPage";
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
        : <section id="mission" aria-label="任务执行台"><p>正在等待服务端任务快照…</p></section>}
      <CreateJobPage />
      <PlatformsPage />
      <JobHistoryPage />
      <ArtifactsPage />
    </AppShell>
  );
}
