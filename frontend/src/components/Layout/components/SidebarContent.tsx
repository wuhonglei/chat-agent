import { Conversations } from "@ant-design/x";
import { Spin } from "antd";
import React, { useCallback, useRef } from "react";
import SimpleBar from "simplebar-react";
import { useConversationInfiniteScroll, useSidebarContent } from "../hooks";
import CompressResultModal from "../modals/CompressResultModal";
import RenameModal from "../modals/RenameModal";
import UserAccount from "./UserAccount";

export interface SidebarContentProps {
  /** 小屏下点击对话项后收起侧栏，由 MainLayout 注入 */
  onAfterActiveChange?: () => void;
}

const SidebarContent: React.FC<SidebarContentProps> = ({ onAfterActiveChange }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { loadingMore, noMore } = useConversationInfiniteScroll(containerRef);

  const {
    items,
    menu,
    groupable,
    activeKey,
    editConversionInfo,
    setEditConversionInfo,
    compressResult,
    setCompressResult,
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
      <SimpleBar
        className="flex-1 h-0"
        scrollableNodeProps={{
          ref: containerRef,
          className: "outline-none",
        }}
      >
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
        {noMore && <div className="text-black-tertiary text-center text-sm">暂无更多数据</div>}
      </SimpleBar>
      <UserAccount />
      {editConversionInfo && (
        <RenameModal
          open
          title={editConversionInfo.title}
          onCancel={() => setEditConversionInfo(null)}
          onOk={title => handleEditConversationTitle({ id: editConversionInfo.id, title })}
        />
      )}
      <CompressResultModal
        open={Boolean(compressResult)}
        result={compressResult}
        onClose={() => setCompressResult(null)}
      />
    </>
  );
};

export default React.memo(SidebarContent);
