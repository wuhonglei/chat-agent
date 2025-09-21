import { CheckOutlined, CopyOutlined } from "@ant-design/icons";
import { Button } from "antd";
import useCopyClick from "antd/es/typography/hooks/useCopyClick";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import styles from "./css/NormalCode.module.css";
import classNames from "classnames";

type Props = {
  language: string;
  style?: React.CSSProperties;
  children: string;
};

const customStyle = {
  backgroundColor: "#F8F9FA",
  border: "none",
  borderRadius: "12px",
  paddingTop: 32 + 16,
};

export default function NormalCode({ children, language, style }: Props) {
  const { copied, onClick: onCopyClick } = useCopyClick({
    copyConfig: { text: children },
  });
  return (
    <div className="relative">
      <div
        className={classNames(
          "absolute top-0 left-0 right-0 h-8 flex items-center justify-between font-mono shadow-xs",
          styles["code-meta"]
        )}
      >
        <span className="text-sm">{language}</span>
        <Button
          type="text"
          size="small"
          className="p-0"
          onClick={() => onCopyClick()}
          title={copied ? "已复制" : "复制"}
          icon={copied ? <CheckOutlined /> : <CopyOutlined />}
        >
          复制
        </Button>
      </div>
      <SyntaxHighlighter
        style={vs}
        PreTag={"div"}
        children={children}
        language={language}
        customStyle={{ ...customStyle, ...style }}
      />
    </div>
  );
}
