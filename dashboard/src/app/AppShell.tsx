import type { PropsWithChildren } from "react";
import { Badge, Text } from "@fluentui/react-components";
import type { WorkspaceId } from "./useWorkspace";

const navigation: ReadonlyArray<{ id: WorkspaceId; label: string }> = [
  { id: "mission", label: "任务作战台" },
  { id: "create", label: "新建任务" },
  { id: "platforms", label: "平台与登录" },
  { id: "history", label: "任务历史" },
  { id: "artifacts", label: "产物库" },
];

export function AppShell({ children, activeWorkspace = "mission" }: PropsWithChildren<{ activeWorkspace?: WorkspaceId }>) {
  return <div className="cyber-shell">
    <aside className="cyber-nav">
      <div className="cyber-brand">DISTILL // ANYONE</div>
      <nav aria-label="主导航">
        {navigation.map((item) => <a key={item.id} href={`#${item.id}`} aria-current={item.id === activeWorkspace ? "page" : undefined}>
          {item.label}
        </a>)}
      </nav>
    </aside>
    <section className="cyber-main">
      <header className="workspace-header">
        <div>
          <Badge appearance="outline" color="success" className="engine-state">本地引擎在线</Badge>
          <Text as="h1" size={700} block>蒸馏作战台</Text>
        </div>
        <Text className="workspace-caption">本地内容蒸馏控制台</Text>
      </header>
      {children}
    </section>
  </div>;
}
