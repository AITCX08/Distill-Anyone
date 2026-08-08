import { Text } from "@fluentui/react-components";
import { useEffect, useMemo, useRef } from "react";

export const MAX_TRACE_ENTRIES = 100;
export const MAX_TRACE_LINE_LENGTH = 1000;

const FOLLOW_TAIL_TOLERANCE = 24;

export function shouldFollowLogTail({
  scrollHeight,
  scrollTop,
  clientHeight,
}: {
  scrollHeight: number;
  scrollTop: number;
  clientHeight: number;
}): boolean {
  return scrollHeight - scrollTop - clientHeight <= FOLLOW_TAIL_TOLERANCE;
}

export function LiveTrace({ entries }: { entries: readonly string[] }) {
  const outputRef = useRef<HTMLPreElement>(null);
  const visibleEntries = useMemo(
    () => entries.slice(-MAX_TRACE_ENTRIES).map((entry) => entry.slice(0, MAX_TRACE_LINE_LENGTH)),
    [entries],
  );
  const output = visibleEntries.join("\n");

  useEffect(() => {
    const element = outputRef.current;
    if (element && shouldFollowLogTail(element)) element.scrollTop = element.scrollHeight;
  }, [output]);

  return (
    <section className="live-trace" aria-label="实时日志">
      <div className="live-trace__heading">
        <div><Text className="metric">执行日志</Text><Text as="h2" size={400}>实时日志</Text></div>
        <Text className="metric">{visibleEntries.length} 条</Text>
      </div>
      {visibleEntries.length > 0
        ? <pre ref={outputRef} role="log" aria-live="polite" aria-label="实时任务日志">{output}</pre>
        : <Text className="live-trace__empty">服务端尚未发送任务日志。</Text>}
    </section>
  );
}
