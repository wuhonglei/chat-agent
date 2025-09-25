import React from "react";
import { Button, ButtonProps } from "antd";
import useCopyClick from "antd/es/typography/hooks/useCopyClick";
import { CheckOutlined } from "@ant-design/icons";
import CopyIcon from "@/assets/svg/CopyIcon.svg?react";

interface CopyButtonProps extends ButtonProps {
  text: string;
}

const CopyButton = (props: CopyButtonProps) => {
  const { children = "复制", text, icon = <CopyIcon />, ...rest } = props;
  const { copied, onClick: onCopyClick } = useCopyClick({
    copyConfig: { text },
  });

  return (
    <Button
      type="text"
      size="small"
      className="p-0"
      onClick={() => onCopyClick()}
      title={copied ? "已复制" : "复制"}
      icon={copied ? <CheckOutlined /> : icon}
      {...rest}
    >
      {children}
    </Button>
  );
};

export default React.memo(CopyButton);
