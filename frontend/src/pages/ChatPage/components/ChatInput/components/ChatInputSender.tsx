import { FileOutlined } from "@ant-design/icons";
import { Sender, Suggestion, type SenderProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { GetRef } from "antd";
import React from "react";
import styles from "../css/index.module.css";
import type { MentionTriggerInfo } from "../hooks/useAttachmentMention";

export interface ChatInputSenderProps extends Omit<SenderProps, "onChange" | "value"> {
  value?: string;
  onChange?: (value: string) => void;
  hasMentionableAttachments: boolean;
  getSuggestionItems: (query: string) => Array<{ value: string; label: string }>;
  onContentChangeWithMention: (
    nextValue: string,
    onChange: ((value: string) => void) | undefined,
    onTrigger: (info: MentionTriggerInfo | false) => void
  ) => void;
  onMentionSelect: (
    blockId: string,
    currentValue: string,
    onChange: ((value: string) => void) | undefined
  ) => void;
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

    const handleSelect = useMemoizedFn((blockId: string) => {
      onMentionSelect(blockId, value ?? "", onChange);
    });


    if (!hasMentionableAttachments) {
      return (
        <Sender
          {...senderProps}
          ref={ref}
          value={value}
          onKeyDown={onKeyDown}
          onChange={nextValue => onChange?.(nextValue)}
        />
      );
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
          {({ onTrigger, onKeyDown: onSuggestionKeyDown }) => (
            <Sender
              {...senderProps}
              ref={ref}
              value={value}
              onChange={nextValue => {
                onContentChangeWithMention(nextValue, onChange, onTrigger);
              }}
              onKeyDown={event => {
                onSuggestionKeyDown(event);
                onKeyDown?.(event);
              }}
            />
          )}
        </Suggestion>
      </div>
    );
  }
);

ChatInputSender.displayName = "ChatInputSender";

export default React.memo(ChatInputSender);
