import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";

type Props = {
  language: string;
  children: string | string[];
};

const customStyle = {
  backgroundColor: "#F8F9FA",
  border: "none",
  borderRadius: "12px",
  marginTop: 0,
};

export default function NormalCode({ children, language }: Props) {
  return (
    <SyntaxHighlighter
      style={vs}
      PreTag="div"
      children={children}
      language={language}
      customStyle={customStyle}
    />
  );
}
