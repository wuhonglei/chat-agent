import { FileOutlined } from "@ant-design/icons";
import { Sender, Suggestion, type SenderProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { GetRef } from "antd";
import React from "react";
import styles from "../css/index.module.css";
import type { MentionSelectResult, MentionTriggerInfo } from "../hooks/useAttachmentMention";

/** 稳定空数组，开启词槽模式且避免父组件重渲染时丢失 runtime insert 的 tags */
const EMPTY_SLOT_CONFIG: NonNullable<SenderProps["slotConfig"]> = [];

export interface ChatInputSenderProps extends Omit<SenderProps, "onChange" | "value" | "slotConfig"> {
  value?: string;
  onChange?: (value: string) => void;
  hasMentionableAttachments: boolean;
  getSuggestionItems: (query: string) => Array<{ value: string; label: string }>;
  onContentChangeWithMention: (
    nextValue: string,
    onChange: ((value: string) => void) | undefined,
    onTrigger: (info: MentionTriggerInfo | false) => void
  ) => void;
  onMentionSelect: (blockId: string, currentValue: string) => MentionSelectResult | null;
}

const ChatInputSender = React.forwardRef<GetRef<typeof Sender>, ChatInputSenderProps>(
  (
    {
      value,
      onChange,
      hasMentionableAttachments,
      getSuggestionItems,
      onContentChangeWithMention,
      onMentionSelect,
      onKeyDown,
      ...senderProps
    },
    ref
  ) => {
    const rootRef = React.useRef<HTMLDivElement>(null);
    const senderRef = React.useRef<GetRef<typeof Sender>>(null);
    const onTriggerRef = React.useRef<(info: MentionTriggerInfo | false) => void>(() => {});
    const suppressMentionTriggerRef = React.useRef(false);
    const lastEmittedValueRef = React.useRef(value ?? "");

    const setSenderRef = useMemoizedFn((instance: GetRef<typeof Sender> | null) => {
      senderRef.current = instance;
      if (typeof ref === "function") {
        ref(instance);
      } else if (ref) {
        ref.current = instance;
      }
    });

    const syncFormValue = useMemoizedFn((nextValue: string) => {
      lastEmittedValueRef.current = nextValue;
      onChange?.(nextValue);
    });

    const closeMentionPanel = useMemoizedFn(() => {
      suppressMentionTriggerRef.current = true;
      onTriggerRef.current(false);
      // insert 的 onChange 在 setTimeout(0) 中触发，需延后解除抑制
      window.setTimeout(() => {
        suppressMentionTriggerRef.current = false;
      }, 0);
    });

    // 词槽模式下 value 无效；外部（如欢迎页 Prompts）写入 Form 时需同步到 Sender
    React.useEffect(() => {
      const nextValue = value ?? "";
      if (nextValue === lastEmittedValueRef.current) {
        return;
      }
      lastEmittedValueRef.current = nextValue;
      const sender = senderRef.current;
      if (!sender) {
        return;
      }
      sender.clear();
      if (nextValue) {
        sender.insert([{ type: "text", value: nextValue }]);
      }
    }, [value]);

    const handleSelect = useMemoizedFn((blockId: string) => {
      const currentValue = senderRef.current?.getValue()?.value ?? value ?? "";
      const result = onMentionSelect(blockId, currentValue);
      closeMentionPanel();
      if (!result) {
        return;
      }
      // insert 会异步触发 onChange，由 syncFormValue 回写 Form
      senderRef.current?.insert?.([result.tagSlot], "cursor", result.replaceCharacters);
    });

    const wrapOnTrigger = useMemoizedFn((onTrigger: (info: MentionTriggerInfo | false) => void) => {
      return (info: MentionTriggerInfo | false) => {
        if (suppressMentionTriggerRef.current && info !== false) {
          return;
        }
        onTrigger(info);
      };
    });

    const renderSender = (options?: {
      onTrigger?: (info: MentionTriggerInfo | false) => void;
      onSuggestionKeyDown?: (event: React.KeyboardEvent) => void;
    }) => (
      <Sender
        {...senderProps}
        ref={setSenderRef}
        slotConfig={EMPTY_SLOT_CONFIG}
        onChange={nextValue => {
          if (options?.onTrigger) {
            onContentChangeWithMention(nextValue, syncFormValue, wrapOnTrigger(options.onTrigger));
            return;
          }
          syncFormValue(nextValue);
        }}
        onKeyDown={event => {
          options?.onSuggestionKeyDown?.(event);
          onKeyDown?.(event);
        }}
      />
    );

    if (!hasMentionableAttachments) {
      return renderSender();
    }

    return (
      <div ref={rootRef}>
        <Suggestion
          items={info =>
            getSuggestionItems(info?.query ?? "").map(item => ({
              ...item,
              icon: <FileOutlined />,
            }))
          }
          onSelect={handleSelect}
          classNames={{ popup: styles.mentionPopup }}
          styles={{ popup: { maxWidth: 320 } }}
          getPopupContainer={() => rootRef.current ?? document.body}
        >
          {({ onTrigger, onKeyDown: onSuggestionKeyDown }) => {
            onTriggerRef.current = onTrigger;
            return renderSender({ onTrigger, onSuggestionKeyDown });
          }}
        </Suggestion>
      </div>
    );
  }
);

ChatInputSender.displayName = "ChatInputSender";

export default React.memo(ChatInputSender);
