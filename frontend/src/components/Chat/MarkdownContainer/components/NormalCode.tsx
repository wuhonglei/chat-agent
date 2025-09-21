import { CopyOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import styles from "./css/NormalCode.module.css";
import classNames from "classnames";

const { Text } = Typography;

type Props = {
  language: string;
  style?: React.CSSProperties;
  children: string;
};

const customStyle = {
  backgroundColor: "#F8F9FA",
  border: "none",
  borderRadius: "12px",
  paddingTop: 40,
};

export default function NormalCode({ children, language, style }: Props) {
  return (
    <div className="relative">
      <div
        className={classNames(
          "absolute top-0 left-0 right-0 h-10 flex items-center justify-between font-mono ",
          styles["code-meta"]
        )}
      >
        <span className="text-sm text-gray-600">{language}</span>
        <Text copyable={{ text: children }} />
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
