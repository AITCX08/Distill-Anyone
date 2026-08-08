import { MissionControlPage } from "../features/mission-control/MissionControlPage";
import { useMissionControl } from "../features/mission-control/useMissionControl";
import { CreateJobPage } from "../features/create-job/CreateJobPage";
import { PlatformsPage } from "../features/platforms/PlatformsPage";
import { JobHistoryPage } from "../features/job-history/JobHistoryPage";
import { ArtifactsPage } from "../features/artifacts/ArtifactsPage";
import { AppShell } from "./AppShell";
import { useWorkspace } from "./useWorkspace";

export function App() {
  const mission = useMissionControl();
  const workspace = useWorkspace();

  return (
    <AppShell activeWorkspace={workspace}>
      {workspace === "mission" && (mission
        ? <MissionControlPage
          snapshot={mission.snapshot}
          job={mission.job}
          traceEntries={mission.traceEntries}
          onJobUpdated={mission.updateJob}
        />
        : <section id="mission" aria-label="任务执行台"><p>正在等待服务端任务快照…</p></section>)}
      {workspace === "create" && <CreateJobPage />}
      {workspace === "platforms" && <PlatformsPage />}
      {workspace === "history" && <JobHistoryPage />}
      {workspace === "artifacts" && <ArtifactsPage />}
    </AppShell>
  );
}
