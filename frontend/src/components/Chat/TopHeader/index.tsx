import { App, Layout } from "antd";
import { ConversationInfo } from "@/interfaces";
import HoverButton from "./HoverButton";
import { TitleCreatedBy } from "@/constants";
import { useAppDispatch } from "@/store/hooks";
import { useMemoizedFn } from "ahooks";
import { updateConversationInfo } from "@/store/slices/conversationSlice";
import { XProvider } from "@ant-design/x";

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
    <XProvider
      theme={{
        components: {
          Layout: {
            headerBg: "white",
          },
        },
      }}
    >
      <Header
        style={{ height: 60 }}
        className="flex justify-center items-center"
      >
        {conversationInfo && (
          <HoverButton title={conversationInfo.title} onConfirm={handleEdit} />
        )}
      </Header>
    </XProvider>
  );
}
