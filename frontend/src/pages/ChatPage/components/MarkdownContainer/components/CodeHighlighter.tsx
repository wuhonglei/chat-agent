import {
  CodeHighlighterProps,
  CodeHighlighter as XCodeHighlighter,
} from "@ant-design/x";
import React from "react";
import CustomHeader from "./CustomHeader";

type Props = CodeHighlighterProps & {
  header?: React.ReactNode;
};

const CodeHighlighter = ({ header, ...restProps }: Props) => {
  const props: Omit<CodeHighlighterProps, "children"> = {
    highlightProps: {},
  };
  if (header) {
    props.header = <CustomHeader>{header}</CustomHeader>;
  }

  return <XCodeHighlighter {...props} {...restProps} />;
};

export default React.memo(CodeHighlighter);
