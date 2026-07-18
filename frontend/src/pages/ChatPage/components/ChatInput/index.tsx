import { useChatState, useIsSmallScreen } from "@/hooks";
import { ChatInputFormValues, SendMessageOptions } from "@/interfaces";
import { type UserAttachmentBlock } from "@/interfaces/contentBlock";
import { isPlainEnter } from "@/utils";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { UploadFile } from "antd";
import { App, ConfigProvider, Form, FormInstance, GetProp, GetRef } from "antd";
import classNames from "classnames";
import React from "react";
import ChatInputFooter from "./components/ChatInputFooter";
import ChatInputSender from "./components/ChatInputSender";
import ChatInputSenderHeader from "./components/ChatInputSenderHeader";
import { sortAttachmentsByImageFirst, withServerAttachmentPreview } from "./components/utils";
import { names } from "./constant";
import styles from "./css/index.module.css";
import {
  useButtonState,
  useFormValuesChange,
  useLockedAgentMode,
  useModelImageSupport,
} from "./hooks";
import { useAttachmentMention } from "./hooks/useAttachmentMention";
import {
  CHAT_ATTACHMENT_ACCEPT,
  CHAT_ATTACHMENT_ACCEPT_PDF_ONLY,
  MAX_CHAT_ATTACHMENTS,
  areAttachmentsReady,
  attachmentItemsHasImage,
  getAttachmentBlocks,
  getChatAttachmentValidationError,
  isImageFile,
  isStreamingState,
} from "./util";

interface ChatInputProps {
  conversationId?: string;
  ensureConversationId?: () => Promise<string>;
  isStreaming?: boolean;
  hasImageMessage?: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (values: ChatInputFormValues, options?: SendMessageOptions) => void;
  onStop?: () => void;
  form: FormInstance<ChatInputFormValues>;
}

const ChatInput: React.FC<ChatInputProps> = ({
  conversationId,
  ensureConversationId,
  onSend,
  onStop,
  isStreaming,
  hasImageMessage = false,
  className,
  style,
  form,
}) => {
  const { message } = App.useApp();
  const content = Form.useWatch(names.content, form);
  const agentMode = Form.useWatch(names.agentMode, form);
  const modelId = Form.useWatch(names.modelId, form);
  const { messages } = useChatState(conversationId ?? "");
  const [attachmentItems, setAttachmentItems] = React.useState<GetProp<AttachmentsProps, "items">>(
    []
  );
  const senderRef = React.useRef<GetRef<typeof Sender>>(null);
  const attachmentsRef = React.useRef<GetRef<typeof Attachments>>(null);
  const ignoreAttachmentChangeRef = React.useRef(false);

  const {
    mentionedBlocks,
    mentionableAttachments,
    getSuggestionItems,
    handleContentChange,
    handleMentionSelect,
    resetMentionedBlocks,
  } = useAttachmentMention({ messages, attachmentItems });

  const enableAttachmentChange = useMemoizedFn(() => {
    ignoreAttachmentChangeRef.current = false;
  });

  const handleAttachmentItemsChange = useMemoizedFn(
    (fileList: GetProp<AttachmentsProps, "items">) => {
      if (ignoreAttachmentChangeRef.current) {
        return;
      }
      const normalizedFileList = fileList.map(file =>
        withServerAttachmentPreview(file as UploadFile<UserAttachmentBlock>)
      );
      setAttachmentItems(sortAttachmentsByImageFirst(normalizedFileList));
    }
  );

  const resetAttachments = useMemoizedFn(() => {
    ignoreAttachmentChangeRef.current = true;
    setAttachmentItems([]);
  });

  const buttonState = useButtonState(content, isStreaming, attachmentItems);
  const isSmallScreen = useIsSmallScreen();
  const { onValuesChange } = useFormValuesChange(form);
  const canUploadImage = useModelImageSupport(modelId);
  const hasImageAttachment = attachmentItemsHasImage(attachmentItems);
  const hasImageContext = hasImageAttachment || hasImageMessage;
  const isAgentModeLocked = Boolean(conversationId) && messages.length > 0;
  const lockedAgentMode = useLockedAgentMode({ messages, isAgentModeLocked, agentMode, form });

  const handleValuesChange = useMemoizedFn(
    (changedFields: Partial<ChatInputFormValues>, allFields: ChatInputFormValues) => {
      onValuesChange(changedFields, allFields);
      const hasAgentModeChanged = Object.prototype.hasOwnProperty.call(changedFields, "agentMode");
      const nextAgentMode = changedFields.agentMode;

      if (
        !isAgentModeLocked ||
        !hasAgentModeChanged ||
        typeof lockedAgentMode === "undefined" ||
        nextAgentMode === lockedAgentMode
      ) {
        return;
      }
      form.setFieldValue(names.agentMode, lockedAgentMode);
      message.warning("首条消息发送后不可切换 Agent 模式");
    }
  );

  const handleSend = useMemoizedFn(() => {
    const fieldValues = form.getFieldsValue();
    const text = (fieldValues.content || "").trim();
    if (!text) {
      return;
    }
    if (!areAttachmentsReady(attachmentItems)) {
      message.warning("附件正在上传，请稍候");
      return;
    }
    const attachmentBlocks = getAttachmentBlocks(attachmentItems);
    onSend(
      {
        ...fieldValues,
        content: text,
      },
      {
        attachmentBlocks,
        mentionedBlocks: mentionedBlocks.length > 0 ? mentionedBlocks : undefined,
      }
    );
    senderRef.current?.clear();
    form.resetFields([names.content]);
    resetAttachments();
    resetMentionedBlocks();
  });

  const handlePressEnter = useMemoizedFn((event: React.KeyboardEvent<Element>) => {
    if (!isPlainEnter(event)) {
      return;
    }
    if (isSmallScreen) {
      return false;
    }
    if (isStreaming) {
      event.preventDefault();
      message.warning("当前消息正在生成，请先点击停止");
      return false;
    }
    event.preventDefault();
    handleSend();
  });

  const handleBtnClick = useMemoizedFn(() => {
    if (isStreamingState(buttonState)) {
      onStop?.();
      return;
    }

    handleSend();
  });

  const openAttachmentPicker = useMemoizedFn(() => {
    enableAttachmentChange();
    queueMicrotask(() => {
      attachmentsRef.current?.select({
        accept: canUploadImage ? CHAT_ATTACHMENT_ACCEPT : CHAT_ATTACHMENT_ACCEPT_PDF_ONLY,
        multiple: true,
      });
    });
  });

  const handlePasteFile = useMemoizedFn((files: FileList) => {
    enableAttachmentChange();
    let nextCount = attachmentItems.length;
    for (const file of files) {
      if (!canUploadImage && isImageFile(file)) {
        message.warning("当前模型不支持图片，请切换支持图片的模型后再上传");
        continue;
      }
      const error = getChatAttachmentValidationError(file, nextCount);
      if (error) {
        message.warning(error);
        if (nextCount >= MAX_CHAT_ATTACHMENTS) {
          break;
        }
        continue;
      }
      attachmentsRef.current?.upload(file);
      nextCount += 1;
    }
  });

  return (
    <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 0 } } }}>
      <Form
        form={form}
        style={{
          padding: isSmallScreen ? "0 8px" : undefined,
          ...style,
        }}
        layout="horizontal"
        onValuesChange={handleValuesChange}
        className={classNames("flex flex-col gap-3", className)}
      >
        <Form.Item name={names.content}>
          <ChatInputSender
            ref={senderRef}
            hasMentionableAttachments={mentionableAttachments.length > 0}
            getSuggestionItems={getSuggestionItems}
            onContentChangeWithMention={handleContentChange}
            onMentionSelect={handleMentionSelect}
            header={
              <ChatInputSenderHeader
                conversationId={conversationId}
                ensureConversationId={ensureConversationId}
                attachmentsRef={attachmentsRef}
                attachmentItems={attachmentItems}
                onAttachmentItemsChange={handleAttachmentItemsChange}
                onAttachmentAddStart={enableAttachmentChange}
                canUploadImage={canUploadImage}
              />
            }
            suffix={false}
            // SlotTextArea 在 submitType=enter 时会拦截回车并清除 <br>；移动端改为 shiftEnter 以允许换行
            submitType={isSmallScreen ? "shiftEnter" : "enter"}
            onPasteFile={handlePasteFile}
            onKeyDown={handlePressEnter}
            placeholder="发送消息"
            className={styles.container}
            autoSize={{ minRows: 2, maxRows: 6 }}
            style={{
              borderColor: "#d9d9d9",
              boxShadow: "none",
              overflow: "hidden",
            }}
            footer={() => (
              <ChatInputFooter
                buttonState={buttonState}
                hasImageContext={hasImageContext}
                isAgentModeLocked={isAgentModeLocked}
                onPrimaryClick={handleBtnClick}
                onOpenAttachmentPicker={openAttachmentPicker}
              />
            )}
          />
        </Form.Item>
      </Form>
    </ConfigProvider>
  );
};

export default React.memo(ChatInput);
