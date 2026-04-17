import { DownOutlined, UpOutlined } from "@ant-design/icons";
import { CodeHighlighterProps, CodeHighlighter as XCodeHighlighter } from "@ant-design/x";
import { Button } from "antd";
import classNames from "classnames";
import React from "react";
import CustomHeader from "../CustomHeader";
import { useCodeFold } from "./hooks";
import styles from "./index.module.css";

type Props = CodeHighlighterProps & {
  header?: React.ReactNode;
  /** 限制代码区域最大高度；超出时默认出现纵向滚动条，底部可展开为完整高度 */
  maxHeight?: number | string;
};

const CodeHighlighter = ({
  header,
  maxHeight,
  classNames: classNamesProp,
  styles: stylesProp,
  style,
  ...restProps
}: Props) => {
  const codeContent = restProps.children;

  const {
    rootRef,
    expanded,
    setExpanded,
    mergedClassNames,
    mergedStyles,
    maxHeightCss,
    showFoldBottom,
    canToggle,
    showBottomFade,
  } = useCodeFold({
    maxHeight,
    codeContent,
    classNamesProp,
    stylesProp,
  });

  const props: Omit<CodeHighlighterProps, "children"> = {
    highlightProps: {},
    prismLightMode: false,
  };
  if (header) {
    props.header = <CustomHeader>{header}</CustomHeader>;
  }

  const highlighter = (
    <XCodeHighlighter {...props} {...restProps} classNames={mergedClassNames} styles={mergedStyles} style={style} />
  );

  if (!maxHeightCss) {
    return highlighter;
  }

  return (
    <div ref={rootRef} className={styles.foldRoot}>
      {highlighter}
      {showFoldBottom && (
        <div
          onClick={() => setExpanded(v => !v)}
          className={classNames(styles.foldBottom, showBottomFade && styles.foldBottomFade)}
        >
          {canToggle && (
            <Button
              type="text"
              className={styles.toggleWrap}
              icon={expanded ? <UpOutlined /> : <DownOutlined />}
              aria-label={expanded ? "收起代码块" : "展开完整代码"}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default React.memo(CodeHighlighter);
