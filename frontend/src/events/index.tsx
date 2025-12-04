import { useMemoizedFn } from "ahooks";
import mitt, { Emitter } from "mitt";
import { useEffect } from "react";
export enum EventType {
  ToolCallDone = "toolCallDone",
  ReasoningDone = "reasoningDone",
  ChangeConversion = "changeConversion", // 切换对话
  BlockCollapse = "blockCollapse", // 块折叠 或展开
}

type Events = {
  [EventType.ToolCallDone]: void;
  [EventType.ReasoningDone]: void;
  [EventType.ChangeConversion]: void;
  [EventType.BlockCollapse]: boolean;
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
) {
  const callbackMemoized = useMemoizedFn(callback);

  useEffect(() => {
    emitter.on(eventType, callbackMemoized);
    return () => {
      emitter.off(eventType, callbackMemoized);
    };
  }, [eventType, callbackMemoized]);
}

/**
 * 使用全局 emitter 订阅指定事件，并在组件卸载或依赖变更时自动注销。
 * @param eventType - 要订阅的事件类型
 * @param callback - 事件触发时执行的回调
 * @returns void（该 hook 内部通过 useEffect 处理注册与清理）
 */
export function useEmitterWithCondition<T extends EventType>(
  eventType: T,
  callback: (value: Events[T]) => void,
  shouldListen: boolean
) {
  const callbackMemoized = useMemoizedFn(callback);

  useEffect(() => {
    if (shouldListen) {
      emitter.on(eventType, callbackMemoized);
    } else {
      emitter.off(eventType, callbackMemoized);
    }

    return () => {
      emitter.off(eventType, callbackMemoized);
    };
  }, [eventType, callbackMemoized, shouldListen]);
}
