import { EventType, useEmitter } from "@/events";
import { DownOutlined } from "@ant-design/icons";
import { useDebounceFn, useMemoizedFn, useThrottleFn } from "ahooks";
import { Button } from "antd";
import React, { useEffect, useState } from "react";

type Props = {
  className?: string;
  visibilityHeight: number;
  containerRef: React.RefObject<HTMLElement | null>;
};

export default function FloatButtonBottom({
  containerRef,
  visibilityHeight,
}: Props) {
  const [visible, setVisible] = useState<boolean>(false);

  const onScrollHandler = useMemoizedFn(() => {
    const container = containerRef.current;
    if (!container) return;
    const distanceToBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    setVisible(distanceToBottom >= visibilityHeight);
  });
  const { run: onScrollThrottled } = useThrottleFn(onScrollHandler, {
    wait: 100,
  });
  const { run: onScrollDebounced } = useDebounceFn(onScrollHandler, {
    wait: 500,
  });
  useEmitter(EventType.BlockCollapse, onScrollDebounced);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.addEventListener("scroll", onScrollThrottled, {
      passive: true, // 表示回调中不会执行 preventDefault()
    } as AddEventListenerOptions);

    return () => {
      container?.removeEventListener("scroll", onScrollThrottled);
    };
  }, [onScrollThrottled, containerRef]);

  const scrollToBottom = useMemoizedFn(() => {
    containerRef.current?.scrollTo({
      top: containerRef.current?.scrollHeight,
      behavior: "smooth",
    });
    setVisible(false);
  });

  if (!visible) return null;

  return (
    <Button
      shape="circle"
      icon={<DownOutlined />}
      style={{
        float: "right",
        position: "sticky",
        bottom: 0,
        zIndex: 10,
      }}
      onClick={scrollToBottom}
    />
  );
}
