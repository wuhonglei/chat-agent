import { TitleCreatedBy } from "@/constants";
import { ConversationInfo } from "@/interfaces";
import { useAppDispatch } from "@/store/hooks";
import { updateConversationInfo } from "@/store/slices/conversationSlice";
import { useMemoizedFn } from "ahooks";
import { App, Layout } from "antd";
import HoverButton from "./HoverButton";

const { Header } = Layout;

type Props = {
  conversationInfo: ConversationInfo | null;
};

export default function TopHeader({ conversationInfo }: Props) {
  const dispatch = useAppDispatch();
  const { message } = App.useApp();

  const handleEdit = useMemoizedFn(async (title: string) => {
    await dispatch(
      updateConversationInfo({
        title,
        id: conversationInfo!.id,
        createdBy: TitleCreatedBy.User,
      })
    ).unwrap();
    message.success("重命名成功");
  });

  return (
    <Header style={{ height: 60, backgroundColor: "white" }} className="flex justify-center items-center">
      {conversationInfo && <HoverButton title={conversationInfo.title} onConfirm={handleEdit} />}
    </Header>
  );
}
