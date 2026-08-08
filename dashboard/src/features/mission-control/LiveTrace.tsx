import { Card, Text } from "@fluentui/react-components";

export const MAX_TRACE_ENTRIES = 100;
export const MAX_TRACE_LINE_LENGTH = 1000;

export function LiveTrace({ entries }: { entries: readonly string[] }) {
  const visibleEntries = entries.slice(-MAX_TRACE_ENTRIES).map((entry) => entry.slice(0, MAX_TRACE_LINE_LENGTH));

  return (
    <section aria-label="实时日志">
      <Card>
        <Text as="h2" size={400}>实时日志</Text>
        {visibleEntries.length > 0
          ? <pre aria-live="polite">{visibleEntries.join("\n")}</pre>
          : <Text>暂时没有任务日志。</Text>}
      </Card>
    </section>
  );
}
