import SquareIcon from "@/assets/svg/SquareIcon.svg?react";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import CustomButton from "@/components/common/CustomButton";
import { useIsSmallScreen } from "@/hooks";
import { ChatInputFormValues, SendMessageOptions } from "@/interfaces";
import { ImageBlock } from "@/interfaces/contentBlock";
import { fileAPI } from "@/services/file";
import { isInputEnter } from "@/utils";
import { ArrowUpOutlined, PaperClipOutlined } from "@ant-design/icons";
import { Attachments, AttachmentsProps, Sender } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { Button, ConfigProvider, Form, FormInstance, GetProp, GetRef } from "antd";
import classNames from "classnames";
import React from "react";
import ToolsSetting from "./ToolsSetting";
import { names } from "./constant";
import styles from "./css/index.module.css";
import { useButtonState, useFormValuesChange } from "./hooks";
import { isButtonDisabled, isStreamingState } from "./util";

interface ChatInputProps {
  isStreaming?: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (values: ChatInputFormValues, options?: SendMessageOptions) => void;
  onStop?: () => void;
  form: FormInstance<ChatInputFormValues>;
}

function imageBlocksFromAttachmentItems(items: GetProp<AttachmentsProps, "items"> | undefined): ImageBlock[] {
  if (!items?.length) {
    return [];
  }
  const out: ImageBlock[] = [];
  for (const item of items) {
    if (item.status !== "done" || item.response == null) {
      continue;
    }
    const r = item.response as unknown;
    if (
      typeof r === "object" &&
      r !== null &&
      "type" in r &&
      (r as ImageBlock).type === "image" &&
      "id" in r &&
      "url" in r &&
      "size" in r &&
      "mime" in r
    ) {
      out.push(r as ImageBlock);
    }
  }
  return out;
}

const ChatInput: React.FC<ChatInputProps> = ({ onSend, onStop, isStreaming, className, style, form }) => {
  const content = Form.useWatch(names.content, form);
  const [attachmentItems, setAttachmentItems] = React.useState<GetProp<AttachmentsProps, "items">>([]);
  const senderRef = React.useRef<GetRef<typeof Sender>>(null);
  const attachmentsRef = React.useRef<GetRef<typeof Attachments>>(null);

  const hasAttachmentItems = attachmentItems.length > 0;

  const hasReadyImages = imageBlocksFromAttachmentItems(attachmentItems).length > 0;
  const hasPendingUploads = Boolean(attachmentItems?.some(item => item.status === "uploading"));

  const buttonState = useButtonState(content, isStreaming, {
    hasReadyImages,
    hasPendingUploads,
  });
  const isSmallScreen = useIsSmallScreen();
  const { values, onValuesChange } = useFormValuesChange(form);

  const senderHeader = (
    <Sender.Header
      styles={{
        header: {
          display: "none",
        },
        content: {
          padding: 0,
        },
      }}
      style={{ border: "none" }}
      open
      closable={false}
      forceRender
    >
      <Attachments
        ref={attachmentsRef}
        accept="image/*"
        styles={{
          placeholder: {
            padding: 0,
            border: "none",
          },
          upload: {
            display: "none",
          },
          list: {
            padding: 0,
          },
          root: hasAttachmentItems
            ? {
                padding: 12,
              }
            : undefined,
        }}
        items={attachmentItems}
        placeholder={undefined}
        onChange={({ fileList }) => setAttachmentItems(fileList)}
        customRequest={async options => {
          const { file, onError, onSuccess } = options;
          try {
            const block = await fileAPI.uploadChatImage(file as File);
            onSuccess?.(block);
          } catch (e) {
            onError?.(e as Error);
          }
        }}
        getDropContainer={() => document.body}
      />
    </Sender.Header>
  );

  const handleSend = useMemoizedFn(() => {
    const fieldValues = form.getFieldsValue();
    const text = (fieldValues.content || "").trim();
    const imageBlocks = imageBlocksFromAttachmentItems(attachmentItems);
    if (!text && imageBlocks.length === 0) {
      return;
    }
    onSend(
      {
        ...fieldValues,
        content: text,
      },
      { imageBlocks }
    );
    form.resetFields([names.content]);
    setAttachmentItems([]);
  });

  const handlePressEnter = useMemoizedFn((event: React.KeyboardEvent<Element>) => {
    if (!isInputEnter(event)) {
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

  return (
    <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 0 } } }}>
      <Form
        form={form}
        style={style}
        layout="horizontal"
        onValuesChange={onValuesChange}
        className={classNames("flex flex-col gap-3", className)}
      >
        <Form.Item name={names.content}>
          <Sender
            ref={senderRef}
            header={senderHeader}
            suffix={false}
            onPasteFile={files => {
              for (const file of files) {
                attachmentsRef.current?.upload(file);
              }
            }}
            onKeyDown={handlePressEnter}
            placeholder="发送消息"
            className={styles.container}
            autoSize={{ minRows: 2, maxRows: 6 }}
            style={{
              borderColor: "#d9d9d9",
              boxShadow: "none",
              overflow: "hidden",
            }}
            footer={() => {
              return (
                <div className="flex items-center gap-2 justify-between">
                  <div className="flex items-center gap-2">
                    <Button
                      type="text"
                      style={{ fontSize: 16 }}
                      icon={<PaperClipOutlined />}
                      aria-label="添加图片"
                      onClick={() => {
                        queueMicrotask(() => {
                          attachmentsRef.current?.select({
                            accept: "image/*",
                            multiple: true,
                          });
                        });
                      }}
                    />
                    <Form.Item trigger="onClick" initialValue={false} valuePropName="active" name={names.thinkMode}>
                      <CustomButton size="middle" icon={<ThinkModeIcon />} tooltip="先思考后回答, 解决推理问题">
                        深度思考
                      </CustomButton>
                    </Form.Item>
                    <Form.Item hidden name={names.mcpAutoMode}>
                      <span />
                    </Form.Item>
                    <Form.Item hidden name={names.sourceConfig}>
                      <span />
                    </Form.Item>
                    <ToolsSetting values={values} />
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="middle"
                      shape="round"
                      type="primary"
                      icon={isStreamingState(buttonState) ? <SquareIcon /> : <ArrowUpOutlined />}
                      onClick={handleBtnClick}
                      disabled={isButtonDisabled(buttonState)}
                    />
                  </div>
                </div>
              );
            }}
          />
        </Form.Item>
      </Form>
    </ConfigProvider>
  );
};

export default React.memo(ChatInput);
