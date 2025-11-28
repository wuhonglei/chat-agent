import { EventType, useEmitter } from "@/events";
import { DownOutlined } from "@ant-design/icons";
import { useDebounceFn, useMemoizedFn, useThrottleFn } from "ahooks";
import { Button } from "antd";
import React, { useEffect, useState } from "react";

type Props = {
  className?: string;
  visibilityHeight: number;
  containerRef: React.RefObject<HTMLElement>;
};

export default function FloatButtonBottom({
  containerRef,
  visibilityHeight,
}: Props) {
  const [visible, setVisible] = useState<boolean>(false);

  const onWheelHandler = useMemoizedFn(() => {
    const container = containerRef.current;
    if (!container) return;
    const distanceToBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    setVisible(distanceToBottom >= visibilityHeight);
  });
  const { run: onWheelThrottled } = useThrottleFn(onWheelHandler, {
    wait: 100,
  });
  const { run: onWheelDebounced } = useDebounceFn(onWheelHandler, {
    wait: 500,
  });
  useEmitter(EventType.BlockCollapse, onWheelDebounced);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.addEventListener("wheel", onWheelThrottled, {
      passive: true, // 表示回调中不会执行 preventDefault()
    } as AddEventListenerOptions);

    return () => {
      container?.removeEventListener("wheel", onWheelThrottled);
    };
  }, [onWheelThrottled, containerRef]);

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
