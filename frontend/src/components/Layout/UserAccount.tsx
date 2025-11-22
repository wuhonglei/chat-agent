import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  LogoutOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Conversation, Conversations, ConversationsProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { MenuInfo } from "rc-menu/lib/interface";
import { Avatar, App } from "antd";
import React, { useMemo, useState } from "react";
import { logout } from "@/store/slices/userSlice";
import { toLoginPage } from "@/utils/location";
import { authHeader } from "@/constants";
import SettingModal from "./modals/SettingModal";

export default function UserAccount() {
  const userDetail = useAppSelector(state => state.user.userDetail);
  const dispatch = useAppDispatch();
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);

  const items = useMemo(() => {
    const items: Conversation[] = [
      {
        id: "user",
        key: `/user`,
        label: (
          <div className="flex items-center gap-2">
            <Avatar
              size="small"
              src={userDetail?.avatar}
              icon={<UserOutlined />}
            />
            <span className=" text-gray-600">{userDetail?.name}</span>
          </div>
        ),
      },
    ];
    return items;
  }, [userDetail]);

  const menu: ConversationsProps["menu"] = useMemoizedFn(
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    (_conversation: Conversation) => ({
      items: [
        {
          label: "设置",
          key: "setting",
          icon: <SettingOutlined />,
        },
        {
          label: "退出登录",
          key: "logout",
          icon: <LogoutOutlined />,
        },
      ],
      trigger: (
        _conversation: Conversation,
        info: { originNode: React.ReactNode }
      ) => {
        // 克隆 originNode 并移除 stopPropagation，确保点击图标也能触发菜单
        const clonedNode = React.isValidElement(info.originNode)
          ? React.cloneElement(info.originNode as React.ReactElement, {
              onClick: () => {
                // 不阻止事件冒泡，让 Dropdown 能够接收到点击事件
                // 移除原来的 stopPropagation
              },
            })
          : info.originNode;

        return (
          <div className="absolute inset-0 flex justify-end pr-2">
            {clonedNode}
          </div>
        );
      },
      onClick: async (menuInfo: MenuInfo) => {
        menuInfo.domEvent.stopPropagation();
        if (menuInfo.key === "setting") {
          setOpen(true);
        } else if (menuInfo.key === "logout") {
          await dispatch(logout()).unwrap();
          authHeader.removeAuthorizationHeader();
          message.success("退出登录成功");
          setTimeout(() => {
            toLoginPage(window.location.href);
          }, 300);
        }
      },
    })
  );

  return (
    <>
      <Conversations
        items={items}
        menu={menu}
        activeKey={""}
        classNames={{
          item: "relative",
        }}
      />
      {open && (
        <SettingModal
          open={open}
          data={userDetail}
          onCancel={() => setOpen(false)}
        />
      )}
    </>
  );
}
