import { useThrottleFn } from "ahooks";
import { useEffect, useState } from "react";

export function useContainerWidth(target: HTMLElement | null | undefined) {
  const [containerWidth, setContainerWidth] = useState(0);
  useEffect(() => {
    if (!target) return;
    setContainerWidth(target.clientWidth);
  }, [target]);

  const { run } = useThrottleFn(
    () => {
      if (!target) return;
      setContainerWidth(target.clientWidth);
    },
    { wait: 100 }
  );

  useEffect(() => {
    window.addEventListener("resize", run);
    return () => {
      window.removeEventListener("resize", run);
    };
  }, [run]);

  return containerWidth;
}
