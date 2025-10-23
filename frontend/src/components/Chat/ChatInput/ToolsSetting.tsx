import { Avatar, Form, Popover, Switch } from "antd";
import CustomButton from "@/components/common/CustomButton";
import SettingIcon from "@/assets/svg/SettingIcon.svg?react";
import React, { useState, useRef, useMemo } from "react";
import { useMemoizedFn } from "ahooks";
import { useAppSelector } from "@/store/hooks";
import { names } from "./constant";
import classNames from "classnames";

const ToolsSetting = () => {
  const [open, setOpen] = useState(false);
  const mcpConfig = useAppSelector(state => state.global.mcpConfig);
  const buttonRef = useRef<HTMLDivElement>(null);
  const mcpAutoMode = Form.useWatch<boolean>(names.mcpAutoMode);
  const sourceConfig = Form.useWatch(names.sourceConfig);
  const icons = useMemo(() => {
    return mcpConfig
      .filter(item => sourceConfig?.[item.id])
      .map(item => item.icon);
  }, [sourceConfig, mcpConfig]);

  const handleOpenChange = useMemoizedFn(newState => {
    setOpen(newState);
  });

  return (
    <Popover
      open={open}
      placement="topLeft"
      trigger={["click"]}
      onOpenChange={handleOpenChange}
      getPopupContainer={() => buttonRef.current || document.body}
      content={
        <>
          <Form.Item
            colon={false}
            label={<span className="font-bold">智能选择工具</span>}
            valuePropName="checked"
            name={names.mcpAutoMode}
          >
            <Switch />
          </Form.Item>
          {mcpConfig.map(item => (
            <section
              key={item.id}
              className={classNames(
                "flex items-center justify-between gap-4 h-8 rounded-lg ml-2 p-2 pr-2 hover:bg-blue-100 transition duration-300"
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
                    <span className={mcpAutoMode ? "text-gray-300" : ""}>
                      {item.name}
                    </span>
                  </div>
                }
                labelAlign="left"
                labelCol={{ span: 18 }}
                wrapperCol={{ span: 6 }}
                className="w-full"
                valuePropName="checked"
                name={[...names.sourceConfig, item.id]}
              >
                <Switch disabled={mcpAutoMode} />
              </Form.Item>
            </section>
          ))}
        </>
      }
    >
      <CustomButton
        bordered
        ref={buttonRef}
        size="middle"
        className="gap-px"
        active={mcpAutoMode}
      >
        <SettingIcon className="text-base" />
        {mcpAutoMode ? (
          <>智能选择</>
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
