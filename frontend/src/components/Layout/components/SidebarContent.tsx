import { Conversations } from "@ant-design/x";
import { Spin } from "antd";
import React, { useCallback, useRef } from "react";
import SimpleBar from "simplebar-react";
import { useConversationInfiniteScroll, useSidebarContent } from "../hooks";
import RenameModal from "../modals/RenameModal";
import UserAccount from "./UserAccount";

export interface SidebarContentProps {
  /** 小屏下点击对话项后收起侧栏，由 MainLayout 注入 */
  onAfterActiveChange?: () => void;
}

const SidebarContent: React.FC<SidebarContentProps> = ({ onAfterActiveChange }) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { loadingMore } = useConversationInfiniteScroll(scrollContainerRef);

  const {
    items,
    menu,
    groupable,
    activeKey,
    editConversionInfo,
    setEditConversionInfo,
    handleMenuClick,
    handleEditConversationTitle,
  } = useSidebarContent();

  const onActiveChange = useCallback(
    (pathname: string) => {
      handleMenuClick(pathname);
      onAfterActiveChange?.();
    },
    [handleMenuClick, onAfterActiveChange]
  );

  return (
    <>
      <div ref={scrollContainerRef} className="flex-1 min-h-0 flex flex-col">
        <SimpleBar className="flex-1 h-0">
          <Conversations
            items={items}
            menu={menu}
            groupable={groupable}
            activeKey={activeKey}
            onActiveChange={onActiveChange}
          />
          {loadingMore && (
            <div className="flex justify-center py-3">
              <Spin size="small" />
            </div>
          )}
        </SimpleBar>
      </div>
      <UserAccount />
      {editConversionInfo && (
        <RenameModal
          open
          title={editConversionInfo.title}
          onCancel={() => setEditConversionInfo(null)}
          onOk={title => handleEditConversationTitle({ id: editConversionInfo.id, title })}
        />
      )}
    </>
  );
};

export default React.memo(SidebarContent);
