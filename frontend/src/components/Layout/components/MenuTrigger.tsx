import React, { forwardRef } from "react";

type Props = {
  children?: React.ReactNode;
  onClick?: () => void;
};

const MenuTrigger = forwardRef<HTMLDivElement, Props>(({ children, onClick }: Props, ref) => {
  // 克隆 originNode 并移除 stopPropagation，确保点击图标也能触发菜单
  const clonedNode = React.isValidElement(children)
    ? React.cloneElement(children as React.ReactElement<{ onClick?: () => void }>, {
        onClick: () => {
          // 不阻止事件冒泡，让 Dropdown 能够接收到点击事件
        },
      })
    : children;

  return (
    <div ref={ref} className="absolute inset-0 flex justify-end pr-2" onClick={onClick}>
      {clonedNode}
    </div>
  );
});

export default React.memo(MenuTrigger);
