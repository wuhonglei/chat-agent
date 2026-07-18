import { useRequest } from "ahooks";
import { useCallback, useEffect, useRef, useState } from "react";

async function fetchAsArrayBuffer(url: string): Promise<ArrayBuffer> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "文件不存在" : `加载失败 (${res.status})`);
  }
  return res.arrayBuffer();
}

export function useDocxDocumentPreview(docxUrl: string, enabled: boolean, container: HTMLElement | null) {
  const [reloadToken, setReloadToken] = useState(0);
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
      const buffer = await fetchAsArrayBuffer(docxUrl);
      if (gen !== renderGen.current) {
        return null;
      }
      const { renderAsync } = await import("docx-preview");
      if (gen !== renderGen.current) {
        return null;
      }
      container.replaceChildren();
      await renderAsync(buffer, container, undefined, {
        className: "docx-preview-body",
        inWrapper: true,
        breakPages: true,
        ignoreWidth: true,
      });
      return true;
    },
    {
      ready: Boolean(enabled && docxUrl && container),
      refreshDeps: [docxUrl, enabled, container, reloadToken],
    }
  );

  useEffect(() => {
    return () => {
      renderGen.current += 1;
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
    error: error ? (error instanceof Error ? error.message : "Word 预览失败") : null,
    reload,
  };
}
