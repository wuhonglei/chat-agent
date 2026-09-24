import { Alert, Empty, Spin } from "antd";
import mermaid from "mermaid";
import React, { useEffect, useRef, useState } from "react";
import FileSourceEditor from "./FileSourceEditor";
import PreviewModeShell from "./PreviewModeShell";
import type { SelectedFile } from "./types";

const MermaidDiagram: React.FC<{ source: string }> = ({ source }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    let cancelled = false;
    setStatus("loading");
    setError(null);

    const renderId = `mmd-preview-${crypto.randomUUID()}`;
    void (async () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "default",
        });
        const isValid = await mermaid.parse(source, { suppressErrors: true });
        if (!isValid) {
          throw new Error("Mermaid 语法无效");
        }
        const { svg } = await mermaid.render(renderId, source);
        if (cancelled) {
          return;
        }
        container.innerHTML = svg;
        const svgEl = container.querySelector("svg");
        if (svgEl) {
          const { width } = svgEl.viewBox.baseVal;
          svgEl.removeAttribute("height");
          svgEl.setAttribute("width", "100%");
          svgEl.style.display = "block";
          svgEl.style.width = "100%";
          svgEl.style.height = "auto";
          svgEl.style.maxWidth = width > 0 ? `${width}px` : "100%";
          svgEl.style.maxHeight = "none";
        }
        setStatus("ready");
      } catch (err) {
        if (cancelled) {
          return;
        }
        container.innerHTML = "";
        setError(err instanceof Error ? err.message : "Mermaid 渲染失败");
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [source]);

  return (
    <div className="relative min-h-0 flex-1 overflow-x-hidden overflow-y-auto bg-(--ant-color-fill-quaternary)">
      {status === "loading" ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center">
          <Spin />
        </div>
      ) : null}
      {status === "error" ? <Alert type="error" showIcon message={error} className="m-4" /> : null}
      <div ref={containerRef} className={status === "ready" ? "block w-full p-4" : "hidden"} />
    </div>
  );
};

const MermaidFilePreview: React.FC<{ file: SelectedFile }> = ({ file }) => {
  const source = file.content.trim();
  const preview = source ? (
    <MermaidDiagram source={source} />
  ) : (
    <Empty description="暂无可预览内容" className="m-auto" />
  );

  return (
    <PreviewModeShell
      title={file.title}
      preview={preview}
      source={<FileSourceEditor file={file} />}
    />
  );
};

export default MermaidFilePreview;
