import { useThrottleFn } from "ahooks";
import React, { useEffect, useState } from "react";
import { Button } from "antd";
import { DownOutlined } from "@ant-design/icons";

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
  const { run: onWheel } = useThrottleFn(
    () => {
      const container = containerRef.current;
      if (!container) return;
      const distanceToBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight;
      setVisible(distanceToBottom >= visibilityHeight);
    },
    { wait: 100 }
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.addEventListener("wheel", onWheel, {
      passive: true,
    } as AddEventListenerOptions);

    return () => {
      container?.removeEventListener("wheel", onWheel);
    };
  }, [onWheel, containerRef]);

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
      onClick={() => {
        containerRef.current?.scrollTo({
          top: containerRef.current?.scrollHeight,
          behavior: "smooth",
        });
      }}
    />
  );
}
