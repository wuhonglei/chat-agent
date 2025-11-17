import { useEffect, useRef } from "react";
import { ChatMessage } from "@/interfaces";
import { useThrottleFn } from "ahooks";

type Props = {
  messages: ChatMessage[];
  isStreaming: boolean;
  containerRef: React.RefObject<HTMLElement>;
};

export default function AutoScroll({
  messages,
  isStreaming,
  containerRef,
}: Props) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const userScrollUpRef = useRef(false);

  const { run: onWheel } = useThrottleFn(
    (event: WheelEvent) => {
      const container = containerRef.current;
      if (!container) return;

      // 向下滚动
      if (event.deltaY > 0) {
        // 如果用户没有向上滚动过，则维持自动滚动
        if (!userScrollUpRef.current) {
          return;
        }

        const isAtBottom =
          container.scrollTop + container.clientHeight >=
          container.scrollHeight - 10;
        // 当用户滚动到最底部时，恢复自动滚动
        userScrollUpRef.current = !isAtBottom;
      } else {
        userScrollUpRef.current = true;
      }
    },
    {
      wait: 100, // 节流时间
    }
  );

  useEffect(() => {
    if (!isStreaming) {
      userScrollUpRef.current = false;
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    container.addEventListener("wheel", onWheel, {
      passive: true,
    } as AddEventListenerOptions);
    return () =>
      container?.removeEventListener(
        "wheel",
        onWheel as unknown as EventListener
      );
  }, [isStreaming, onWheel, containerRef]);

  useEffect(() => {
    if (messagesEndRef.current && !userScrollUpRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  return <div ref={messagesEndRef} />;
}
