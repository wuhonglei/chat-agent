import CustomButton from "@/components/common/CustomButton";
import { useIsSmallScreen } from "@/hooks";
import { ChatInputConfig } from "@/interfaces";
import { ToolOutlined } from "@ant-design/icons";
import { useMemoizedFn } from "ahooks";
import { Avatar, Form, Popover, Switch } from "antd";
import { SizeType } from "antd/es/config-provider/SizeContext";
import classNames from "classnames";
import React, { useMemo, useRef, useState } from "react";
import { names, websiteBuildModeForcedOffMcpIds } from "../constant";
import { useMCPConfig } from "../hooks";

function isWebsiteBuildForcedOffMcp(id: string): boolean {
  return (websiteBuildModeForcedOffMcpIds as readonly string[]).includes(id);
}

interface ToolsSettingProps {
  size: SizeType;
  values: ChatInputConfig;
  websiteBuildMode: boolean;
}

const ToolsSetting: React.FC<ToolsSettingProps> = ({ values, size, websiteBuildMode }) => {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);
  const mcpAutoMode = Boolean(values.mcpAutoMode);
  const sourceConfig = values.sourceConfig;
  const mcpConfig = useMCPConfig();
  const isSmallScreen = useIsSmallScreen();
  const icons = useMemo(
    () => mcpConfig.filter(item => sourceConfig?.[item.id]).map(item => item.icon),
    [sourceConfig, mcpConfig]
  );

  const handleOpenChange = useMemoizedFn(newState => {
    setOpen(newState);
  });

  return (
    <Popover
      open={open}
      placement="topLeft"
      trigger={["click"]}
      onOpenChange={handleOpenChange}
      getPopupContainer={() => document.body}
      content={
        <>
          <Form.Item
            colon={false}
            valuePropName="checked"
            name={names.mcpAutoMode}
            label={<span className="font-bold">智能选择工具</span>}
          >
            <Switch disabled={websiteBuildMode} />
          </Form.Item>
          {mcpConfig.map(item => (
            <section
              key={item.id}
              className={classNames(
                "flex items-center justify-between gap-4 h-8 rounded-lg ml-2 p-2 pr-2 hover:bg-quaternary transition duration-300"
              )}
            >
              <Form.Item
                tooltip={{
                  title: item.description,
                }}
                colon={false}
                label={
                  <div className="flex items-center gap-2">
                    <img src={item.icon} alt={item.id} className="w-4 h-4" />
                    <span className={mcpAutoMode ? "text-black-tertiary" : ""}>{item.name}</span>
                  </div>
                }
                labelAlign="left"
                labelCol={{ span: 18 }}
                wrapperCol={{ span: 6 }}
                className="w-full"
                valuePropName="checked"
                name={[...names.sourceConfig, item.id]}
              >
                <Switch
                  disabled={mcpAutoMode || !item.online || (websiteBuildMode && isWebsiteBuildForcedOffMcp(item.id))}
                />
              </Form.Item>
            </section>
          ))}
        </>
      }
    >
      <CustomButton bordered={false} ref={buttonRef} size={size} className="gap-px" active>
        <ToolOutlined className="text-base mr-1" />
        {mcpAutoMode ? (
          <>{isSmallScreen ? "" : "智能选择"}</>
        ) : (
          <Avatar.Group>
            {icons.map(icon => (
              <Avatar shape="circle" src={icon} key={icon} size={16} />
            ))}
          </Avatar.Group>
        )}
      </CustomButton>
    </Popover>
  );
};

export default React.memo(ToolsSetting);
