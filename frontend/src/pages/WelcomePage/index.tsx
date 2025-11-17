import ChatInput from "@/pages/ChatPage/components/ChatInput";
import { ChatInputFormValues } from "@/interfaces";
import { Form } from "antd";
import { registerConversation } from "@/store/slices/conversationSlice";

import classNames from "classnames";
import parentStyles from "../ChatPage/index.module.css";
import { useNavigate } from "react-router-dom";
import { useAppDispatch } from "@/store/hooks";
import { useMemoizedFn } from "ahooks";
import { useNewConversation } from "@/hooks";
import { TitleCreatedBy } from "@/constants";
import Title from "antd/es/typography/Title";

export default function EmptyChatPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { setCacheData } = useNewConversation();

  const [form] = Form.useForm<ChatInputFormValues>();
  const handleMessageSend = useMemoizedFn(
    async (values: ChatInputFormValues) => {
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
    }
  );

  return (
    <div className={classNames("h-full bg-white flex", parentStyles.container)}>
      <div
        className={classNames(
          "flex flex-col gap-4 items-center w-full my-auto",
          parentStyles["input-container"]
        )}
      >
        <Title level={3} className="flex items-center gap-4">
          有什么我能帮你的吗？
        </Title>
        <ChatInput form={form} onSend={handleMessageSend} className="w-full" />
      </div>
    </div>
  );
}
