import { ConversationInfo, EditConversationInfo } from "@/interfaces";
import { Button, Layout } from "antd";
import HoverButton from "./HoverButton";
import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import { useWebTitle } from "@/hooks";

type Props = {
  collapsed: boolean;
  onCollapse: () => void;
  onCreateConversion: () => void;
  conversationInfo?: ConversationInfo | null;
  onEdit: (info: EditConversationInfo) => void;
};

const { Header } = Layout;

export default function TopHeader({
  collapsed,
  conversationInfo,
  onEdit,
  onCollapse,
  onCreateConversion,
}: Props) {
  useWebTitle(conversationInfo);

  return (
    <Header
      style={{ height: 60 }}
      className="flex justify-center items-center relative"
    >
      {collapsed && (
        <div className="absolute left-2 md:left-12.5 h-10 flex items-center gap-1 rounded-full border border-gray-200 p-1 shadow">
          <Button
            type="text"
            shape="circle"
            onClick={onCollapse}
            icon={<CollapseIcon className="w-4 h-4" />}
          />
          <Button
            type="text"
            shape="circle"
            onClick={onCreateConversion}
            icon={<NewConversionIcon className="w-4 h-4" />}
          />
        </div>
      )}
      {conversationInfo && (
        <HoverButton
          title={conversationInfo.title}
          onConfirm={newTitle =>
            onEdit({ id: conversationInfo.id, title: newTitle })
          }
        />
      )}
    </Header>
  );
}
