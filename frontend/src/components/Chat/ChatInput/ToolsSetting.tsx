import { Avatar, Dropdown, Form, Switch } from "antd";
import CustomButton from "@/components/common/CustomButton";
import SettingIcon from "@/assets/svg/SettingIcon.svg?react";
import tavilyUrl from "@/assets/imgs/tavily.png";
import confluenceUrl from "@/assets/imgs/confluence.png";
import googleDocsUrl from "@/assets/imgs/googleDocs.png";
import React, { useState, useRef, useMemo } from "react";
import { useMemoizedFn } from "ahooks";
import { names } from "./constant";

const menuItems = [
  {
    label: "联网搜索",
    key: names.webSearch.at(-1),
    name: names.webSearch,
    icon: tavilyUrl,
  },
  {
    label: "Confluence",
    key: names.confluence.at(-1),
    name: names.confluence,
    icon: confluenceUrl,
  },
  {
    label: "Google Docs",
    key: names.googleDocs.at(-1),
    name: names.googleDocs,
    icon: googleDocsUrl,
  },
];

const ToolsSetting = () => {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);
  const sourceConfig = Form.useWatch("source_config");
  const icons = useMemo(() => {
    return menuItems
      .filter(item => sourceConfig?.[item.key!])
      .map(item => item.icon);
  }, [sourceConfig]);

  const handleOpenChange = useMemoizedFn((newState, info) => {
    if (info.source === "menu") {
      return;
    }
    setOpen(newState);
  });

  return (
    <Dropdown
      open={open}
      onOpenChange={handleOpenChange}
      trigger={["click"]}
      getPopupContainer={() => buttonRef.current || document.body}
      menu={{
        items: menuItems.map(item => ({
          label: (
            <section className="flex items-center justify-between gap-4 h-7">
              <div className="flex items-center gap-2">
                <img src={item.icon} alt={item.label} className="w-4 h-4" />
                <span>{item.label}</span>
              </div>
              <Form.Item noStyle valuePropName="checked" name={item.name}>
                <Switch />
              </Form.Item>
            </section>
          ),
          key: item.key!,
        })),
      }}
    >
      <CustomButton bordered ref={buttonRef} size="small" className="gap-px">
        <SettingIcon className="text-base" />
        <Avatar.Group>
          {icons.map(icon => (
            <Avatar shape="circle" src={icon} key={icon} size={16} />
          ))}
        </Avatar.Group>
      </CustomButton>
    </Dropdown>
  );
};

export default React.memo(ToolsSetting);
