import { useIsScrollByUser } from "@/hooks/ui";
import { ChatMessage } from "@/interfaces";
import { useThrottleFn } from "ahooks";
import { useEffect, useRef } from "react";

type Props = {
  messages: ChatMessage[];
  isStreaming: boolean;
  containerRef: React.RefObject<HTMLElement | null>;
};

export default function AutoScroll({
  messages,
  isStreaming,
  containerRef,
}: Props) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const _isScrollByUser = useIsScrollByUser(containerRef); // 滚动是否由用户触发
  const isScrollByUserRef = useRef(isStreaming && _isScrollByUser);
  const userScrollUpRef = useRef(false); // 用户是否向上滚动

  useEffect(() => {
    isScrollByUserRef.current = isStreaming && _isScrollByUser;
  }, [isStreaming, _isScrollByUser]);

  const lastScrollTopRef = useRef(0);

  const { run: onScroll } = useThrottleFn(
    () => {
      const container = containerRef.current;
      if (!container) return;

      const currentScrollTop = container.scrollTop;
      const scrollDelta = currentScrollTop - lastScrollTopRef.current;
      lastScrollTopRef.current = currentScrollTop;

      if (!isScrollByUserRef.current) return;

      // 滚动条向上滚动(用户看到上面的内容)
      if (scrollDelta < 0) {
        userScrollUpRef.current = true;
      } else if (scrollDelta >= 0) {
        // 滚动条向下滚动(用户看到下面的内容)
        const isAtBottom =
          container.scrollTop + container.clientHeight >=
          container.scrollHeight - 10;
        // 当用户滚动到最底部时，恢复自动滚动
        userScrollUpRef.current = !isAtBottom;
      }
    },
    { wait: 100 }
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!isStreaming) {
      /**
       * 流式输出结束，重置用户滚动标志。这样下次流式输出开始时，会自动滚动到最底部
       * 延迟是为了避免下面的 useEffect 触发，导致滚动到最底部
       */
      setTimeout(() => {
        userScrollUpRef.current = false;
      }, 1000);
      return;
    }
    if (!container) return;

    // 初始化滚动位置
    lastScrollTopRef.current = container.scrollTop;

    container.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", onScroll);
    };
  }, [isStreaming, onScroll, containerRef]);

  useEffect(() => {
    if (!userScrollUpRef.current && messagesEndRef.current) {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 0);
    }
  }, [messages, userScrollUpRef]);

  return <div ref={messagesEndRef} />;
}
