import { Button, Text } from "@fluentui/react-components";

export function MissionEmptyState() {
  return (
    <section id="mission" className="mission-empty" aria-label="任务执行台">
      <div className="mission-empty__signal" aria-hidden="true">◇</div>
      <Text className="metric">等待新的任务快照</Text>
      <Text as="h2" size={600}>当前没有正在追踪的蒸馏任务</Text>
      <Text>本地引擎已连接。创建任务后，这里会显示逐集进度、执行日志与可验证的剩余时间。</Text>
      <Button as="a" href="#create" appearance="primary">创建蒸馏任务</Button>
    </section>
  );
}
