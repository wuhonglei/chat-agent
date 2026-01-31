import { DEFAULT_THRESHOLD } from "@/constants";
import { useDebounceFn, useSize, useThrottleFn } from "ahooks";
import { useEffect, useMemo, useState } from "react";

export function useIsSmallScreen() {
  const { width } = useSize(document.body) || {};
  return useMemo(() => (width ? width <= DEFAULT_THRESHOLD : false), [width]);
}

/**
 * 判断滚动事件是否由用户手动触发
 * @param containerRef
 * @returns boolean
 */
export function useIsScrollByUser(containerRef: React.RefObject<HTMLElement | null>) {
  const [scrollByUser, setScrollByUser] = useState(false);

  // 桌面端：滚动停止后延迟重置（等待惯性滚动结束）
  const { run: onWheelEnd, cancel: cancelWheelEnd } = useDebounceFn(
    () => {
      setScrollByUser(false);
    },
    { wait: 500 }
  );

  // 桌面端：处理 wheel 事件
  const { run: onWheel } = useThrottleFn(
    () => {
      const container = containerRef.current;
      if (!container) return;
      cancelWheelEnd(); // 取消之前的重置
      setScrollByUser(true);
      onWheelEnd(); // 延迟重置
    },
    {
      wait: 100, // 节流时间
    }
  );

  // 移动端：触摸结束（延迟重置，等待惯性滚动结束）
  const { run: onTouchEnd, cancel: cancelTouchEnd } = useDebounceFn(
    () => {
      setScrollByUser(false);
    },
    { wait: 500 }
  );

  // 移动端：触摸开始
  const { run: onTouchStart } = useThrottleFn(
    () => {
      cancelTouchEnd();
      setScrollByUser(true);
    },
    { wait: 50 }
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 桌面端：监听 wheel 事件
    container.addEventListener("wheel", onWheel, {
      passive: true,
    } as AddEventListenerOptions);

    // 移动端：监听触摸事件
    container.addEventListener("touchstart", onTouchStart, {
      passive: true,
    } as AddEventListenerOptions);
    container.addEventListener("touchend", onTouchEnd, {
      passive: true,
    } as AddEventListenerOptions);

    return () => {
      container.removeEventListener("wheel", onWheel as unknown as EventListener);
      container.removeEventListener("touchstart", onTouchStart as unknown as EventListener);
      container.removeEventListener("touchend", onTouchEnd as unknown as EventListener);
      cancelWheelEnd(); // 清理时取消延迟重置
    };
  }, [onWheel, onTouchStart, onTouchEnd, cancelWheelEnd, containerRef]);

  return scrollByUser;
}
