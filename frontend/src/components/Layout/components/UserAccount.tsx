import { authHeader } from "@/constants";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { logout } from "@/store/slices/userSlice";
import { toLoginPage } from "@/utils/location";
import { LogoutOutlined, SettingOutlined, UserOutlined } from "@ant-design/icons";
import { ConversationItemType, Conversations, ConversationsProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { App, Avatar, type MenuProps } from "antd";
import React, { useMemo, useState } from "react";
import SettingModal from "../modals/SettingModal";
import MenuTrigger from "./MenuTrigger";

export default function UserAccount() {
  const userDetail = useAppSelector(state => state.user.userDetail);
  const dispatch = useAppDispatch();
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);

  const items = useMemo(() => {
    const items: ConversationItemType[] = [
      {
        id: "user",
        key: `/user`,
        label: (
          <div className="flex items-center gap-2">
            <Avatar size="small" src={userDetail?.avatar} icon={<UserOutlined />} />
            <span className="text-black-secondary">{userDetail?.name}</span>
          </div>
        ),
      },
    ];
    return items;
  }, [userDetail]);

  const menu: ConversationsProps["menu"] = useMemoizedFn(
    // oxlint-disable-next-line @typescript-eslint/no-unused-vars
    (_conversation: ConversationItemType) => ({
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
      trigger: (_conversation: ConversationItemType, info: { originNode: React.ReactNode }) => (
        <MenuTrigger>{info.originNode}</MenuTrigger>
      ),
      onClick: async (menuInfo: Parameters<NonNullable<MenuProps["onClick"]>>[0]) => {
        menuInfo.domEvent.stopPropagation();
        if (menuInfo.key === "setting") {
          setOpen(true);
        } else if (menuInfo.key === "logout") {
          await dispatch(logout()); // 不论是否成功，都退出登录
          authHeader.removeAuthorizationHeader();
          message.success("退出登录成功");
          setTimeout(() => {
            toLoginPage(location.pathname);
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
      {open && <SettingModal open={open} onCancel={() => setOpen(false)} />}
    </>
  );
}
