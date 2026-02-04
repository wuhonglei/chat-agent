import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import SiteLogo from "@/components/common/SiteLogo";
import SiteTitle from "@/components/common/SiteTitle";
import { Button, theme } from "antd";
import React from "react";
import { Link } from "react-router-dom";

const { useToken } = theme;

export interface SidebarHeaderProps {
  collapsed?: boolean;
  onCollapse: () => void;
  onNewConversation: () => void;
}

const SidebarHeader: React.FC<SidebarHeaderProps> = ({ collapsed, onCollapse, onNewConversation }) => {
  const { token } = useToken();

  return (
    <>
      {collapsed && (
        <div className="fixed left-2 md:left-12.5 top-2.5 h-10 flex items-center gap-1 rounded-full border border-gray-200 p-1 shadow bg-white">
          <Button type="text" shape="circle" onClick={onCollapse} icon={<CollapseIcon className="w-4 h-4" />} />
          <Button
            type="text"
            shape="circle"
            onClick={onNewConversation}
            icon={<NewConversionIcon className="w-4 h-4" />}
          />
        </div>
      )}
      <div className="mx-3 my-4 flex justify-between items-center">
        <Link to="/chat" className="flex items-center gap-2 h-9">
          <SiteLogo size={36} />
          <SiteTitle level={5} />
        </Link>
        <Button
          type="text"
          onClick={onCollapse}
          icon={<CollapseIcon className="w-4 h-4" />}
          style={{ color: token.colorTextDescription }}
        />
      </div>
      <Button size="large" shape="round" className="mx-3" onClick={onNewConversation} icon={<NewConversionIcon />}>
        开启新对话
      </Button>
    </>
  );
};

export default React.memo(SidebarHeader);
