import { ChatInputFormValues, ConversationInfo, SendMessageOptions } from "@/interfaces";
import ChatInput from "@/pages/ChatPage/components/ChatInput";
import { registerConversation } from "@/store/slices/conversationSlice";
import { BulbOutlined, CheckSquareOutlined, CodeOutlined, RocketOutlined } from "@ant-design/icons";
import { Prompts } from "@ant-design/x";
import type { PromptsProps } from "@ant-design/x";
import { Form } from "antd";

import { useNewConversation } from "@/hooks";
import { TitleCreatedBy } from "@/interfaces";
import { useAppDispatch } from "@/store/hooks";
import { useMemoizedFn } from "ahooks";
import Title from "antd/es/typography/Title";
import classNames from "classnames";
import { useNavigate } from "react-router-dom";
import parentStyles from "../ChatPage/index.module.css";
import { useDraftConversation } from "./hooks";

const websiteBuildPromptTextMap: Record<string, string> = {
  "todo-list":
    "请帮我创建一个待办列表网站，包含任务新增、编辑、完成状态切换、优先级与截止日期管理、筛选搜索与本地持久化，并给出页面结构与核心交互说明。",
  "personal-blog":
    "请帮我创建一个个人博客网站，包含首页、文章列表、文章详情、关于我和联系页面，并给出推荐的技术栈、目录结构与核心功能清单。",
  "product-landing-page":
    "请帮我创建一个商品落地页网站，包含商品卖点、功能亮点、价格方案、用户评价、FAQ 和购买 CTA，并给出页面结构与首屏文案示例。",
  dashboard:
    "请帮我创建一个数据仪表盘网站，包含概览卡片、趋势图、筛选器、明细表格和导出功能，并说明前端组件拆分与状态管理方案。",
};

const websiteBuildPromptItems: PromptsProps["items"] = [
  {
    key: "todo-list",
    icon: <CheckSquareOutlined style={{ color: "#13C2C2" }} />,
    label: "创建待办列表",
    description: "搭建支持任务管理、筛选和状态流转的待办应用。",
  },
  {
    key: "personal-blog",
    icon: <CodeOutlined style={{ color: "#1890FF" }} />,
    label: "创建个人博客",
    description: "规划博客站点页面、文章系统与技术实现方案。",
  },
  {
    key: "dashboard",
    icon: <RocketOutlined style={{ color: "#722ED1" }} />,
    label: "创建数据仪表盘",
    description: "设计带图表分析与筛选能力的业务仪表盘应用。",
  },
  {
    key: "product-landing-page",
    icon: <BulbOutlined style={{ color: "#FFD700" }} />,
    label: "创建商品落地页",
    description: "生成一个完整商品落地页的结构、文案与关键模块建议。",
  },
];

export default function EmptyChatPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { setCacheData } = useNewConversation();
  const { draftConversation, ensureDraftConversationId, publishDraftConversation } = useDraftConversation();

  const [form] = Form.useForm<ChatInputFormValues>();
  const agentMode = Form.useWatch("agentMode", form);

  const handleMessageSend = useMemoizedFn(async (values: ChatInputFormValues, options?: SendMessageOptions) => {
    // 如果上传附件时已经创建了草稿会话，则复用该会话。
    let activeConversation: ConversationInfo | null = null;
    if (draftConversation) {
      activeConversation = await publishDraftConversation(draftConversation);
    } else {
      activeConversation = await dispatch(registerConversation({ isActive: true })).unwrap();
    }
    const data = {
      isNewConversation: true,
      values,
      attachmentBlocks: options?.attachmentBlocks,
      mentionedBlocks: options?.mentionedBlocks,
      createdBy: TitleCreatedBy.Default,
      insertAt: Date.now(),
    };
    setCacheData(data);

    // 更新 URL 到新的会话 ID
    navigate(`/chat/${activeConversation.id}`, {
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
        {agentMode ? (
          <Prompts
            wrap={true}
            vertical={false}
            items={websiteBuildPromptItems}
            onItemClick={info => {
              const prompt = websiteBuildPromptTextMap[String(info.data.key)] || "";
              form.setFieldValue("content", prompt);
            }}
          />
        ) : null}
        <ChatInput
          form={form}
          className="w-full"
          onSend={handleMessageSend}
          conversationId={draftConversation?.id}
          ensureConversationId={ensureDraftConversationId}
        />
      </div>
    </div>
  );
}
