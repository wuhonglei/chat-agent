import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import SiteLogo from "@/components/common/SiteLogo";
import SiteTitle from "@/components/common/SiteTitle";
import { SearchOutlined } from "@ant-design/icons";
import { Button, theme } from "antd";
import React from "react";
import { Link } from "react-router-dom";

const { useToken } = theme;

export interface SidebarHeaderProps {
  collapsed?: boolean;
  onCollapse: () => void;
  onNewConversation: () => void;
  onOpenSearch: () => void;
}

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform);
const shortcutHint = isMac ? "⌘K" : "Ctrl K";

const SidebarHeader: React.FC<SidebarHeaderProps> = ({
  collapsed,
  onCollapse,
  onNewConversation,
  onOpenSearch,
}) => {
  const { token } = useToken();

  return (
    <>
      {collapsed && (
        <div className="fixed left-2 md:left-12.5 top-2.5 h-10 flex items-center gap-1 rounded-full border border-gray-200 p-1 shadow bg-white">
          <Button
            type="text"
            shape="circle"
            onClick={onCollapse}
            icon={<CollapseIcon className="w-4 h-4" />}
          />
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
      <div className="mx-3 mb-3">
        <button
          type="button"
          onClick={onOpenSearch}
          className="flex h-9 w-full items-center gap-2 rounded-lg bg-gray-100 px-3 text-left hover:bg-gray-200 transition-colors border-0 cursor-pointer"
        >
          <SearchOutlined className="text-gray-400" />
          <span className="flex-1 text-sm text-gray-400">搜索...</span>
          <span className="text-xs text-gray-400">{shortcutHint}</span>
        </button>
      </div>
      <Button
        size="large"
        shape="round"
        className="mx-3"
        onClick={onNewConversation}
        icon={<NewConversionIcon />}
      >
        开启新对话
      </Button>
    </>
  );
};

export default React.memo(SidebarHeader);
