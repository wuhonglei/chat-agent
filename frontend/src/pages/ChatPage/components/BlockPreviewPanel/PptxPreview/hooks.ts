import { useRequest } from "ahooks";
import { useCallback, useEffect, useRef, useState } from "react";
import { computePdfPageWidth } from "../previewLayout";

type PptxPreviewerInstance = {
  preview: (file: ArrayBuffer) => Promise<unknown>;
  destroy: () => void;
};

async function fetchAsArrayBuffer(url: string): Promise<ArrayBuffer> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "文件不存在" : `加载失败 (${res.status})`);
  }
  return res.arrayBuffer();
}

export function usePptxDocumentPreview(
  pptxUrl: string,
  enabled: boolean,
  container: HTMLElement | null,
  layoutWidth: number
) {
  const [reloadToken, setReloadToken] = useState(0);
  const viewerRef = useRef<PptxPreviewerInstance | null>(null);
  const renderGen = useRef(0);

  const {
    loading,
    error,
    refresh,
  } = useRequest(
    async () => {
      if (!container) {
        return null;
      }
      const gen = ++renderGen.current;
      const buffer = await fetchAsArrayBuffer(pptxUrl);
      if (gen !== renderGen.current) {
        return null;
      }

      viewerRef.current?.destroy();
      viewerRef.current = null;
      container.replaceChildren();

      const { init } = await import("pptx-preview");
      if (gen !== renderGen.current) {
        return null;
      }

      const width = computePdfPageWidth(layoutWidth);
      const height = Math.round((width * 9) / 16);
      const viewer = init(container, {
        width,
        height,
        mode: "slide",
      });
      viewerRef.current = viewer;
      await viewer.preview(buffer);
      return true;
    },
    {
      ready: Boolean(enabled && pptxUrl && container),
      refreshDeps: [pptxUrl, enabled, container, layoutWidth, reloadToken],
    }
  );

  useEffect(() => {
    return () => {
      renderGen.current += 1;
      viewerRef.current?.destroy();
      viewerRef.current = null;
      if (container) {
        container.replaceChildren();
      }
    };
  }, [container]);

  const reload = useCallback(() => {
    setReloadToken(token => token + 1);
    refresh();
  }, [refresh]);

  return {
    loading,
    error: error ? (error instanceof Error ? error.message : "PowerPoint 预览失败") : null,
    reload,
  };
}
