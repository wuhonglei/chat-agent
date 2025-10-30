import mitt, { Emitter } from "mitt";
import { useMemoizedFn } from "ahooks";
import { useEffect } from "react";
export enum EventType {
  ToolCallDone = "toolCallDone",
  ReasoningDone = "reasoningDone",
}

type Events = {
  [EventType.ToolCallDone]: void;
  [EventType.ReasoningDone]: void;
};

export const emitter: Emitter<Events> = mitt<Events>();

/**
 * 使用全局 emitter 订阅指定事件，并在组件卸载或依赖变更时自动注销。
 * @param eventType - 要订阅的事件类型
 * @param callback - 事件触发时执行的回调
 * @returns void（该 hook 内部通过 useEffect 处理注册与清理）
 */
export function useEmitter<T extends EventType>(
  eventType: T,
  callback: (value: Events[T]) => void
): void {
  const callbackMemoized = useMemoizedFn(callback);
  useEffect(() => {
    emitter.on(eventType, callbackMemoized);
    return () => {
      emitter.off(eventType, callbackMemoized);
    };
  }, [eventType, callbackMemoized]);
}
