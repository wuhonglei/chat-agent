import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vs } from "react-syntax-highlighter/dist/esm/styles/prism";
import GrayContainer, { CopyButton } from "./GrayContainer";

type Props = {
  language: string;
  children: string;
  showLanguage?: boolean;
  style?: React.CSSProperties;
};

const customStyle = {
  border: "none",
  borderBottomLeftRadius: "12px",
  borderBottomRightRadius: "12px",
  backgroundColor: "inherit",
};

export default function NormalCode({
  children,
  language,
  showLanguage = true,
  style,
}: Props) {
  return (
    <GrayContainer
      header={
        showLanguage && (
          <>
            <span className="text-sm">{language}</span>
            <CopyButton children={children} />
          </>
        )
      }
    >
      <SyntaxHighlighter
        style={vs}
        PreTag={"div"}
        children={children}
        language={language}
        customStyle={{
          ...customStyle,
          marginTop: showLanguage ? 0 : "0.5em",
          ...style,
        }}
      />
    </GrayContainer>
  );
}
