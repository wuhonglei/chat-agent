import React from "react";
import styles from "./css/GrayContainer.module.css";
import classNames from "classnames";
import { Button } from "antd";
import useCopyClick from "antd/es/typography/hooks/useCopyClick";
import { CheckOutlined, CopyOutlined } from "@ant-design/icons";

type Props = {
  header?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};

type CopyButtonProps = {
  children: string;
};

type LanguageLabelProps = {
  children: string;
  className?: string;
};

export const LanguageLabel = ({ children, className }: LanguageLabelProps) => {
  return <span className={classNames("text-sm", className)}>{children}</span>;
};

export const CopyButton = ({ children }: CopyButtonProps) => {
  const { copied, onClick: onCopyClick } = useCopyClick({
    copyConfig: { text: children },
  });

  return (
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
  );
};

export default function GrayContainer({ header, children, className }: Props) {
  return (
    <div
      className={classNames(
        "relative flex flex-col my-2",
        styles.container,
        className
      )}
    >
      {header && (
        <div
          className={classNames(
            "w-full h-10 flex items-center justify-between font-mono shadow-xs",
            styles["code-meta"]
          )}
        >
          {header}
        </div>
      )}
      {children}
    </div>
  );
}
