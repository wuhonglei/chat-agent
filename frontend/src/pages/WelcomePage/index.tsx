import { ChatInputFormValues, ConversationInfo, SendMessageOptions } from "@/interfaces";
import ChatInput from "@/pages/ChatPage/components/ChatInput";
import { registerConversation } from "@/store/slices/conversationSlice";
import { CheckSquareOutlined, CodeOutlined, FileSearchOutlined, ProfileOutlined } from "@ant-design/icons";
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

const agentSkillPromptTextMap: Record<string, string> = {
  "todo-list":
    "请帮我创建一个待办列表网站，包含任务新增、编辑、完成状态切换、优先级与截止日期管理、筛选搜索与本地持久化，并给出页面结构与核心交互说明。",
  "personal-blog":
    "请帮我创建一个个人博客网站，包含首页、文章列表、文章详情、关于我和联系页面，并给出推荐的技术栈、目录结构与核心功能清单。",
  "deep-research":
    "请帮我深度研究「大语言模型在企业知识管理中的应用」，从技术原理、落地案例、竞品方案、风险与实施路径多个角度系统调研，并给出有来源支撑的结论与建议。",
  "industry-report":
    "请帮我撰写一份关于「中国智能客服市场」的咨询级研究报告，包含市场格局、竞争分析、用户需求、增长驱动因素与战略建议。",
};

const agentSkillPromptItems: PromptsProps["items"] = [
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
    key: "deep-research",
    icon: <FileSearchOutlined style={{ color: "#FA8C16" }} />,
    label: "深度研究主题",
    description: "多角度检索资料，形成有来源支撑的调研结论。",
  },
  {
    key: "industry-report",
    icon: <ProfileOutlined style={{ color: "#722ED1" }} />,
    label: "撰写研究报告",
    description: "输出咨询级行业分析框架、洞察与战略建议。",
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
            items={agentSkillPromptItems}
            onItemClick={info => {
              const prompt = agentSkillPromptTextMap[String(info.data.key)] || "";
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
