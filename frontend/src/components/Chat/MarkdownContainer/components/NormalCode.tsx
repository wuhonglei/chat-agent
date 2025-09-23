import React from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";

type Props = {
  language: string;
  children: string;
  style?: React.CSSProperties;
};

const customStyle = {
  border: "none",
  margin: 0,
  borderBottomLeftRadius: "12px",
  borderBottomRightRadius: "12px",
  backgroundColor: "inherit",
};

const NormalCode = ({ children, language, style }: Props) => {
  return (
    <SyntaxHighlighter
      style={vs}
      PreTag={"div"}
      children={children}
      language={language}
      customStyle={{
        ...customStyle,
        ...style,
      }}
    />
  );
}

export default React.memo(NormalCode);
