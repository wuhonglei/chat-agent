import { useAppSelector } from "@/store/hooks";
import {
  EditOutlined,
  LogoutOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Conversation, Conversations, ConversationsProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { Avatar } from "antd";
import { useMemo } from "react";

export default function UserAccount() {
  const userDetail = useAppSelector(state => state.user.userDetail);

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
            <span className=" text-gray-600">{userDetail?.name || "-"}</span>
          </div>
        ),
      },
    ];
    return items;
  }, [userDetail]);

  const menu: ConversationsProps["menu"] = useMemoizedFn(() => ({
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
    onClick: (menuInfo: MenuInfo) => {},
  }));

  return <Conversations items={items} menu={menu} activeKey={""} />;
}
