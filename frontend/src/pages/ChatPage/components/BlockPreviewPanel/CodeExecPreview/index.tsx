import type { CodeExecBlock, CodeExecStage } from "@/interfaces/contentBlock";
import { CloseOutlined } from "@ant-design/icons";
import { Button, Divider, Tag, Typography } from "antd";
import React from "react";

export interface CodeExecPreviewPanelProps {
  width: number;
  block: CodeExecBlock;
  onClose: () => void;
}

function normalizeStageText(text: string): string {
  // Some runtimes return escaped newlines as literal "\n".
  if (text.includes("\\n") && !text.includes("\n")) {
    return text.replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n");
  }
  return text;
}

function hasStageContent(stage: CodeExecStage | null): boolean {
  if (!stage) {
    return false;
  }
  return Boolean(stage.stdout || stage.stderr || stage.output || stage.code !== null || stage.signal != null);
}

const CodeExecPreviewPanel: React.FC<CodeExecPreviewPanelProps> = ({ block, onClose }) => {
  const { language, version, run, compile } = block;
  const compileHasContent = hasStageContent(compile);
  const runHasContent = hasStageContent(run);

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <div className="flex items-center gap-2">
          <Typography.Text type="secondary">代码运行结果</Typography.Text>
          <Tag>{language}</Tag>
          <Tag>{version}</Tag>
        </div>
        <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-4">
        <Typography.Title level={5}>控制台</Typography.Title>
        <div className="space-y-3 rounded border border-(--ant-color-border-secondary) bg-white p-3">
          <Typography.Text className="block">退出码：{run.code ?? "未知"}</Typography.Text>
          {run.signal != null ? (
            <Typography.Text className="block">Signal：{String(run.signal)}</Typography.Text>
          ) : null}
          {runHasContent ? (
            <>
              {run.stdout ? (
                <>
                  <Typography.Text type="secondary" className="block">
                    stdout
                  </Typography.Text>
                  <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word">
                    {normalizeStageText(run.stdout)}
                  </pre>
                </>
              ) : null}
              {run.stderr ? (
                <>
                  <Typography.Text type="secondary" className="block">
                    stderr
                  </Typography.Text>
                  <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word text-(--ant-color-error)">
                    {normalizeStageText(run.stderr)}
                  </pre>
                </>
              ) : null}
              {run.output && !run.stdout && !run.stderr ? (
                <>
                  <Typography.Text type="secondary" className="block">
                    output
                  </Typography.Text>
                  <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word">
                    {normalizeStageText(run.output)}
                  </pre>
                </>
              ) : null}
            </>
          ) : (
            <Typography.Text type="secondary">代码运行完成，无输出。</Typography.Text>
          )}
        </div>

        {compile ? (
          <>
            <Divider>编译阶段</Divider>
            <div className="space-y-3 rounded border border-(--ant-color-border-secondary) bg-white p-3">
              <Typography.Text className="block">退出码：{compile.code ?? "未知"}</Typography.Text>
              {compile.signal != null ? (
                <Typography.Text className="block">Signal：{String(compile.signal)}</Typography.Text>
              ) : null}
              {compileHasContent ? (
                <>
                  {compile.stdout ? (
                    <>
                      <Typography.Text type="secondary" className="block">
                        stdout
                      </Typography.Text>
                      <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word">
                        {normalizeStageText(compile.stdout)}
                      </pre>
                    </>
                  ) : null}
                  {compile.stderr ? (
                    <>
                      <Typography.Text type="secondary" className="block">
                        stderr
                      </Typography.Text>
                      <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word text-(--ant-color-error)">
                        {normalizeStageText(compile.stderr)}
                      </pre>
                    </>
                  ) : null}
                  {compile.output ? (
                    <>
                      <Typography.Text type="secondary" className="block">
                        output
                      </Typography.Text>
                      <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word">
                        {normalizeStageText(compile.output)}
                      </pre>
                    </>
                  ) : null}
                </>
              ) : (
                <Typography.Text type="secondary">无编译输出。</Typography.Text>
              )}
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
};

export default React.memo(CodeExecPreviewPanel);
