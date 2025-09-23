import { Dropdown } from "antd";
import { Space } from "antd";
import { DownOutlined, GlobalOutlined } from "@ant-design/icons";
import CustomButton from "@/components/CustomButton";
import React from "react";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const ToolsSetting = ({ open, onOpenChange }: Props) => {
  return (
    <Dropdown
      open={open}
      onOpenChange={onOpenChange}
      placement="topRight"
      menu={{
        items: [
          {
            label: (
              <CustomButton
                icon={<GlobalOutlined />}
                active
                size="small"
                className="w-full"
                bordered={false}
              >
                互联网
              </CustomButton>
            ),
            key: "thinkMode",
          },
        ],
      }}
    >
      <a onClick={e => e.preventDefault()}>
        <Space>
          Hover me
          <DownOutlined />
        </Space>
      </a>
    </Dropdown>
  );
};

export default React.memo(ToolsSetting);
