import { ChatInputFormValues } from "@/interfaces";
import ChatInput from "@/pages/ChatPage/components/ChatInput";
import { registerConversation } from "@/store/slices/conversationSlice";
import { Form } from "antd";

import { useNewConversation } from "@/hooks";
import { TitleCreatedBy } from "@/interfaces";
import { useAppDispatch } from "@/store/hooks";
import { useMemoizedFn } from "ahooks";
import Title from "antd/es/typography/Title";
import classNames from "classnames";
import { useNavigate } from "react-router-dom";
import parentStyles from "../ChatPage/index.module.css";

export default function EmptyChatPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { setCacheData } = useNewConversation();

  const [form] = Form.useForm<ChatInputFormValues>();
  const handleMessageSend = useMemoizedFn(async (values: ChatInputFormValues) => {
    // 创建会话
    const { id } = await dispatch(registerConversation()).unwrap();
    const data = {
      isNewConversation: true,
      values,
      createdBy: TitleCreatedBy.Default,
      insertAt: Date.now(),
    };
    setCacheData(data);

    // 更新 URL 到新的会话 ID
    navigate(`/chat/${id}`, {
      replace: true,
    });
  });

  return (
    <div
      // 小屏模式下，输入框在底部, 手机浏览器底部的工具栏会遮挡输入框，所以需要留出空间
      className={classNames("h-full bg-white flex items-end md:items-center pb-14 md:pb-0", parentStyles.container)}
    >
      <div className={classNames("flex flex-col gap-4 items-center w-full", parentStyles["input-container"])}>
        <Title level={3} className="flex items-center gap-4">
          有什么我能帮你的吗？
        </Title>
        <ChatInput form={form} onSend={handleMessageSend} className="w-full" />
      </div>
    </div>
  );
}
