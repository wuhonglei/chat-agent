import { useIsSmallScreen } from "@/hooks";
import { ChatInputFormValues, SendMessageOptions } from "@/interfaces";
import { isPlainEnter } from "@/utils";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { ConfigProvider, Form, FormInstance, GetProp, GetRef, message } from "antd";
import classNames from "classnames";
import React from "react";
import ChatInputFooter from "./components/ChatInputFooter";
import ChatInputSenderHeader from "./components/ChatInputSenderHeader";
import { names } from "./constant";
import styles from "./css/index.module.css";
import { useButtonState, useFormValuesChange, useModelImageSupport } from "./hooks";
import {
  CHAT_ATTACHMENT_ACCEPT,
  CHAT_ATTACHMENT_ACCEPT_PDF_ONLY,
  MAX_CHAT_ATTACHMENTS,
  attachmentItemsHasImage,
  getAttachmentBlocks,
  getChatAttachmentValidationError,
  isImageFile,
  isStreamingState,
} from "./util";

interface ChatInputProps {
  isStreaming?: boolean;
  hasImageMessage?: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (values: ChatInputFormValues, options?: SendMessageOptions) => void;
  onStop?: () => void;
  form: FormInstance<ChatInputFormValues>;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  isStreaming,
  hasImageMessage = false,
  className,
  style,
  form,
}) => {
  const content = Form.useWatch(names.content, form);
  const modelId = Form.useWatch(names.modelId, form);
  const [attachmentItems, setAttachmentItems] = React.useState<GetProp<AttachmentsProps, "items">>([]);
  const senderRef = React.useRef<GetRef<typeof Sender>>(null);
  const attachmentsRef = React.useRef<GetRef<typeof Attachments>>(null);

  const buttonState = useButtonState(content, isStreaming, attachmentItems);
  const isSmallScreen = useIsSmallScreen();
  const { values, onValuesChange } = useFormValuesChange(form);
  const canUploadImage = useModelImageSupport(modelId);
  const hasImageAttachment = attachmentItemsHasImage(attachmentItems);
  const hasImageContext = hasImageAttachment || hasImageMessage;

  const handleSend = useMemoizedFn(() => {
    const fieldValues = form.getFieldsValue();
    const text = (fieldValues.content || "").trim();
    const attachmentBlocks = getAttachmentBlocks(attachmentItems);
    if (!text) {
      return;
    }
    onSend(
      {
        ...fieldValues,
        content: text,
      },
      { attachmentBlocks }
    );
    form.resetFields([names.content]);
    setAttachmentItems([]);
  });

  const handlePressEnter = useMemoizedFn((event: React.KeyboardEvent<Element>) => {
    if (!isPlainEnter(event)) {
      return;
    }
    if (isSmallScreen) {
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
    queueMicrotask(() => {
      attachmentsRef.current?.select({
        accept: canUploadImage ? CHAT_ATTACHMENT_ACCEPT : CHAT_ATTACHMENT_ACCEPT_PDF_ONLY,
        multiple: true,
      });
    });
  });

  const handlePasteFile = useMemoizedFn((files: FileList) => {
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
        onValuesChange={onValuesChange}
        className={classNames("flex flex-col gap-3", className)}
      >
        <Form.Item name={names.content}>
          <Sender
            ref={senderRef}
            header={
              <ChatInputSenderHeader
                attachmentsRef={attachmentsRef}
                attachmentItems={attachmentItems}
                setAttachmentItems={setAttachmentItems}
                canUploadImage={canUploadImage}
              />
            }
            suffix={false}
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
                values={values}
                buttonState={buttonState}
                hasImageContext={hasImageContext}
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
