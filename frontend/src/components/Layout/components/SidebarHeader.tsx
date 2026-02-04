import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import SiteLogo from "@/components/common/SiteLogo";
import SiteTitle from "@/components/common/SiteTitle";
import { Button, theme } from "antd";
import React from "react";
import { Link } from "react-router-dom";

const { useToken } = theme;

export interface SidebarHeaderProps {
  onCollapse: () => void;
  onNewConversation: () => void;
}

const SidebarHeader: React.FC<SidebarHeaderProps> = ({ onCollapse, onNewConversation }) => {
  const { token } = useToken();

  return (
    <>
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
