import type { CodeRuntimeLanguage, PreviewableBlock } from "@/interfaces/contentBlock";
import { codeAPI } from "@/services";
import { PlayCircleOutlined } from "@ant-design/icons";
import { Actions } from "@ant-design/x";
import { useRequest } from "ahooks";
import { Button } from "antd";
import React from "react";

function createCodeExecPreviewBlockId() {
  return `code_exec_preview_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export interface CodeExecHeaderProps {
  language: CodeRuntimeLanguage;
  code: string;
  openPreview: (block: PreviewableBlock) => void;
}

const CodeExecHeader: React.FC<CodeExecHeaderProps> = ({ language, code, openPreview }) => {
  const { runAsync, loading } = useRequest(codeAPI.executeCode, { manual: true });

  const handleRunCode = async () => {
    try {
      const result = await runAsync({ code, language });
      openPreview({
        id: createCodeExecPreviewBlockId(),
        type: "code_exec",
        language,
        code,
        version: result.version,
        run: result.run,
        compile: result.compile,
      });
    } catch {
      // 错误提示由统一请求拦截器处理，这里避免未捕获 Promise 异常
    }
  };

  return (
    <>
      <span className="text-(--ant-color-text-secondary)">{language}</span>
      <div className="flex shrink-0 items-center gap-1">
        <Button
          type="text"
          size="small"
          className="px-1!"
          icon={<PlayCircleOutlined />}
          loading={loading}
          onClick={handleRunCode}
        >
          运行
        </Button>
        <Actions.Copy text={code} />
      </div>
    </>
  );
};

export default React.memo(CodeExecHeader);
