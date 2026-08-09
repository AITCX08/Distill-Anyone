import { MissionControlPage } from "../features/mission-control/MissionControlPage";
import { MissionEmptyState } from "../features/mission-control/MissionEmptyState";
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
          tasks={mission.tasks}
          onTaskUpdated={mission.updateTask}
        />
        : <MissionEmptyState />)}
      {workspace === "create" && <CreateJobPage />}
      {workspace === "platforms" && <PlatformsPage />}
      {workspace === "history" && <JobHistoryPage />}
      {workspace === "artifacts" && <ArtifactsPage />}
    </AppShell>
  );
}
