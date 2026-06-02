import { ChatInputConfig, ChatInputFormValues, ChatMessage } from "@/interfaces";
import { RootState } from "@/store";
import { useAppSelector } from "@/store/hooks";
import { AttachmentsProps } from "@ant-design/x";
import { createSelector } from "@reduxjs/toolkit";
import { useLocalStorageState, useMemoizedFn } from "ahooks";
import { GetProp } from "antd";
import { FormInstance } from "antd/es/form";
import { isEmpty, isEqual, omit, trim } from "lodash-es";
import { useEffect, useMemo } from "react";
import { ButtonState, names } from "./constant";
import { areAttachmentsReady } from "./util";

/**
 * 根据消息内容、附件是否可发送、是否流式传输，返回按钮状态
 */
export function useButtonState(
  content: string,
  isStreaming: boolean | undefined,
  attachmentItems: GetProp<AttachmentsProps, "items">
): ButtonState {
  if (isStreaming) {
    return ButtonState.Streaming;
  }

  if (!trim(content)) {
    return ButtonState.WaitingType;
  }

  // 附件内容为空，用户正在输入
  if (isEmpty(attachmentItems)) {
    return ButtonState.Typing;
  }

  // 所有附件都已上传完成
  if (areAttachmentsReady(attachmentItems)) {
    return ButtonState.Typing;
  }

  return ButtonState.WaitingType;
}

const defaultFormValue: ChatInputConfig = {
  thinkMode: false,
  agentMode: 0,
  modelID: "default",
};

const selectModels = createSelector(
  [(state: RootState) => state.models.models, (state: RootState) => state.models.loaded],
  (models, modelsLoaded) => ({ models, modelsLoaded })
);
export const chatInputFormValuesStorageKey = "chat-input-form-values-v1";

export function useFormValuesChange(form: FormInstance<ChatInputFormValues>) {
  const [formValues, setFormValues] = useLocalStorageState<ChatInputConfig>(chatInputFormValuesStorageKey, {
    defaultValue: defaultFormValue,
  });
  const { models, modelsLoaded } = useAppSelector(selectModels);

  useEffect(() => {
    if (!modelsLoaded || isEmpty(models)) {
      return;
    }
    const defaultModelID = "default";
    setFormValues(pre => {
      const rawPre = pre || defaultFormValue;
      const currentModelID = rawPre.modelID;
      const isValidModelID = Boolean(currentModelID && models.some(item => item.modelId === currentModelID));
      if (isValidModelID) {
        return rawPre;
      }
      return {
        ...rawPre,
        modelID: defaultModelID,
      };
    });
  }, [modelsLoaded, models, setFormValues]);

  const onValuesChange = useMemoizedFn(
    (_changedFields: Partial<ChatInputFormValues>, allFields: ChatInputFormValues) => {
      const changedKeys = Object.keys(_changedFields);
      if (isEqual(changedKeys, names.content)) {
        return;
      }
      setFormValues(pre => {
        const base: ChatInputConfig = {
          ...pre,
          ...omit(allFields, "content"),
        };
        return base;
      });
    }
  );

  useEffect(() => {
    form.setFieldsValue(formValues);
  }, [formValues, form]);

  return {
    onValuesChange,
  };
}

export function useModelImageSupport(modelId: string | undefined): boolean {
  const models = useAppSelector((state: RootState) => state.models.models);
  const selectedModel = models.find(item => item.modelId === modelId);
  return selectedModel?.imageSupport ?? true;
}

export function useLockedAgentMode(params: {
  messages: ChatMessage[];
  isAgentModeLocked: boolean;
  agentMode: ChatInputFormValues["agentMode"] | undefined;
  form: FormInstance<ChatInputFormValues>;
}): ChatInputFormValues["agentMode"] | undefined {
  const { messages, isAgentModeLocked, agentMode, form } = params;
  const lockedAgentMode = useMemo(() => {
    const lastMessage = messages.at(-1);
    const value = lastMessage?.messageMetadata?.agentMode;
    return typeof value === "number" ? value : undefined;
  }, [messages]);

  useEffect(() => {
    if (!isAgentModeLocked || typeof lockedAgentMode === "undefined" || typeof agentMode === "undefined") {
      return;
    }
    if (agentMode !== lockedAgentMode) {
      form.setFieldValue(names.agentMode, lockedAgentMode);
    }
  }, [agentMode, form, isAgentModeLocked, lockedAgentMode]);

  return lockedAgentMode;
}
