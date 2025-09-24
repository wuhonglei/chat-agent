import { Dropdown, Form, Switch } from "antd";
import CustomButton from "@/components/CustomButton";
import SettingIcon from "@/assets/svg/SettingIcon.svg?react";
import tavilyUrl from "@/assets/imgs/tavily.png";
import confluenceUrl from "@/assets/imgs/confluence.png";
import googleDocsUrl from "@/assets/imgs/googleDocs.png";
import React, { useState, useRef } from "react";
import { useMemoizedFn } from "ahooks";
import { names } from "./constant";

const menuItems = [
  {
    label: "互联网",
    key: names.webSearch.join("."),
    icon: tavilyUrl,
  },
  {
    label: "Confluence",
    key: names.confluence.join("."),
    icon: confluenceUrl,
  },
  {
    label: "Google Docs",
    key: names.googleDocs.join("."),
    icon: googleDocsUrl,
  },
];

const ToolsSetting = () => {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);

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
            <section className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <img src={item.icon} alt={item.label} className="w-4 h-4" />
                <span>{item.label}</span>
              </div>
              <Form.Item
                noStyle
                valuePropName="checked"
                name={item.key.split(".")}
              >
                <Switch />
              </Form.Item>
            </section>
          ),
          key: item.key,
        })),
      }}
    >
      <CustomButton ref={buttonRef} bordered={false} size="small">
        <SettingIcon className="text-xl" />
      </CustomButton>
    </Dropdown>
  );
};

export default React.memo(ToolsSetting);
