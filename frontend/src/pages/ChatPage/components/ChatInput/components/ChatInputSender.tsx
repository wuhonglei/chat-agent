import { isPlainEnter } from "@/utils";
import { Sender, Suggestion, type SenderProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { GetRef } from "antd";
import React from "react";
import { getProjectPreviewFileIcon } from "../../BlockPreviewPanel/ProjectPreview/file_icons";
import styles from "../css/index.module.css";
import type { MentionSelectResult, MentionTriggerInfo } from "../hooks/useAttachmentMention";

/** 稳定空数组，开启词槽模式且避免父组件重渲染时丢失 runtime insert 的 tags */
const EMPTY_SLOT_CONFIG: NonNullable<SenderProps["slotConfig"]> = [];

/** contenteditable + pre-wrap 下，末尾单独 \n 不产生可视换行，需用 ZWSP 占住新行 */
const NEWLINE_ZWSP = "\n\u200B";

type SuggestionOption = { value: string; label: string };

function normalizeEditorValue(value: string): string {
  // contenteditable 常把空格写成 NBSP，与 Form 中的普通空格对齐，避免误触发回写清空
  return value.replace(/\u00a0/g, " ");
}

/** 回写 Form / 比较受控值时去掉换行锚点，避免 sync effect 清掉 DOM 中的 ZWSP */
function toFormEditorValue(value: string): string {
  return normalizeEditorValue(value).replace(/\u200B/g, "");
}

/** 保留换行，仅清理零宽字符与统一换行符（SlotTextArea.getCleanedText 会删掉全部 \n） */
function sanitizePastedPlainText(text: string): string {
  return text
    .replace(/\u200B/g, "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n");
}

export interface ChatInputSenderProps extends Omit<
  SenderProps,
  "onChange" | "value" | "slotConfig"
> {
  value?: string;
  onChange?: (value: string) => void;
  hasMentionableAttachments: boolean;
  getSuggestionItems: (query: string) => SuggestionOption[];
  onContentChangeWithMention: (
    nextValue: string,
    onChange: ((value: string) => void) | undefined,
    onTrigger: (info: MentionTriggerInfo | false) => void,
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
    ref,
  ) => {
    const rootRef = React.useRef<HTMLDivElement>(null);
    const senderRef = React.useRef<GetRef<typeof Sender>>(null);
    const onTriggerRef = React.useRef<(info: MentionTriggerInfo | false) => void>(() => {});
    const suppressMentionTriggerRef = React.useRef(false);
    const suppressValueChangeRef = React.useRef(false);
    const lastEmittedValueRef = React.useRef(toFormEditorValue(value ?? ""));
    const suggestionOpenRef = React.useRef(false);
    const suggestionItemsRef = React.useRef<SuggestionOption[]>([]);
    const activeIndexRef = React.useRef(0);

    const setSenderRef = useMemoizedFn((instance: GetRef<typeof Sender> | null) => {
      senderRef.current = instance;
      if (typeof ref === "function") {
        ref(instance);
      } else if (ref) {
        ref.current = instance;
      }
    });

    const syncFormValue = useMemoizedFn((nextValue: string) => {
      if (suppressValueChangeRef.current) {
        return;
      }
      const forForm = toFormEditorValue(nextValue);
      lastEmittedValueRef.current = forForm;
      onChange?.(forForm);
    });

    const closeMentionPanel = useMemoizedFn(() => {
      suppressMentionTriggerRef.current = true;
      onTriggerRef.current(false);
      // insert 的 onChange 在 setTimeout(0) 中触发，需延后解除抑制
      window.setTimeout(() => {
        suppressMentionTriggerRef.current = false;
      }, 0);
    });

    // 词槽模式下 value 无效；仅在外部（如欢迎页 Prompts）写入 Form 时同步到 Sender
    React.useEffect(() => {
      const nextValue = toFormEditorValue(value ?? "");
      if (nextValue === lastEmittedValueRef.current) {
        return;
      }
      const sender = senderRef.current;
      if (!sender) {
        lastEmittedValueRef.current = nextValue;
        return;
      }

      suppressValueChangeRef.current = true;
      lastEmittedValueRef.current = nextValue;
      sender.clear();
      if (nextValue) {
        sender.insert([{ type: "text", value: nextValue }]);
      }
      // clear/insert 会异步触发 onChange，延后解除抑制
      window.setTimeout(() => {
        suppressValueChangeRef.current = false;
      }, 0);
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

    const handleSenderKeyDown = useMemoizedFn(
      (
        event: React.KeyboardEvent,
        options?: {
          onSuggestionKeyDown?: (event: React.KeyboardEvent) => void;
        },
      ) => {
        // Suggestion 基于 Cascader：非可编辑模式下空格会 preventDefault（ARIA combobox），
        // 事件冒泡到 Cascader 根节点后无法输入空格，需拦截冒泡。
        if (event.key === " " || event.code === "Space") {
          event.stopPropagation();
          return;
        }

        // Cascader 会对 Enter preventDefault（甚至打开下拉）；SlotTextArea 在
        // submitType=enter 时还会清掉 <br>。有可 @ 附件时无法 Shift+Enter 换行。
        // 输入区为 pre-wrap，插入 \n 可保留换行且不被 removeSpecificBRs 清除；
        // 末尾补 ZWSP，否则第一次 Shift+Enter 看不见换行（需按两次）。
        if (event.key === "Enter" && event.shiftKey) {
          event.preventDefault();
          event.stopPropagation();
          senderRef.current?.insert?.([{ type: "text", value: NEWLINE_ZWSP }], "cursor");
          return false;
        }

        const items = suggestionItemsRef.current;
        if (suggestionOpenRef.current && items.length > 0) {
          if (event.key === "ArrowDown") {
            activeIndexRef.current = (activeIndexRef.current + 1) % items.length;
            options?.onSuggestionKeyDown?.(event);
            return;
          }
          if (event.key === "ArrowUp") {
            activeIndexRef.current = (activeIndexRef.current - 1 + items.length) % items.length;
            options?.onSuggestionKeyDown?.(event);
            return;
          }
          if (isPlainEnter(event)) {
            // 面板展开时回车选中当前高亮项，不发送消息
            event.preventDefault();
            event.stopPropagation();
            const activeItem = items[activeIndexRef.current] ?? items[0];
            if (activeItem) {
              handleSelect(activeItem.value);
            }
            return false;
          }
        }

        // 普通 Enter 也需拦截冒泡，避免 Cascader 打开下拉或 preventDefault
        if (event.key === "Enter") {
          event.stopPropagation();
        }

        options?.onSuggestionKeyDown?.(event);
        // 必须回传返回值：Sender 以 `false` 跳过 Enter 提交并允许换行
        return onKeyDown?.(event);
      },
    );

    // SlotTextArea 粘贴会先走 getCleanedText（.replace(/\n/g, '')），需在捕获阶段改写
    const handlePasteCapture = useMemoizedFn((event: React.ClipboardEvent) => {
      const text = event.clipboardData?.getData("text/plain");
      if (!text || !/[\r\n]/.test(text)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const sanitized = sanitizePastedPlainText(text);
      if (sanitized) {
        senderRef.current?.insert?.([{ type: "text", value: sanitized }], "cursor");
      }
    });

    const renderSender = (options?: {
      onTrigger?: (info: MentionTriggerInfo | false) => void;
      onSuggestionKeyDown?: (event: React.KeyboardEvent) => void;
    }) => (
      <Sender
        {...senderProps}
        ref={setSenderRef}
        slotConfig={EMPTY_SLOT_CONFIG}
        onChange={(nextValue) => {
          if (options?.onTrigger) {
            onContentChangeWithMention(nextValue, syncFormValue, wrapOnTrigger(options.onTrigger));
            return;
          }
          syncFormValue(nextValue);
        }}
        onKeyDown={(event) => handleSenderKeyDown(event, options)}
      />
    );

    return (
      <div ref={rootRef} onPasteCapture={handlePasteCapture}>
        {hasMentionableAttachments ? (
          <Suggestion
            items={(info) => {
              const list = getSuggestionItems(info?.query ?? "");
              suggestionItemsRef.current = list;
              activeIndexRef.current = 0;
              return list.map((item) => ({
                ...item,
                icon: getProjectPreviewFileIcon(item.label),
              }));
            }}
            onSelect={handleSelect}
            classNames={{ popup: styles.mentionPopup }}
            styles={{ popup: { width: "auto", minWidth: 0, maxWidth: 320 } }}
            getPopupContainer={() => rootRef.current ?? document.body}
          >
            {({ onTrigger, onKeyDown: onSuggestionKeyDown, open }) => {
              onTriggerRef.current = onTrigger;
              suggestionOpenRef.current = open;
              return renderSender({ onTrigger, onSuggestionKeyDown });
            }}
          </Suggestion>
        ) : (
          renderSender()
        )}
      </div>
    );
  },
);

ChatInputSender.displayName = "ChatInputSender";

export default React.memo(ChatInputSender);
