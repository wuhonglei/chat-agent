import { ChatInputConfig, ChatInputFormValues, MCPConfigItem, RetrieverSource } from "@/interfaces";
import { RootState } from "@/store";
import { useAppSelector } from "@/store/hooks";
import { AttachmentsProps } from "@ant-design/x";
import { createSelector } from "@reduxjs/toolkit";
import { useLocalStorageState, useMemoizedFn } from "ahooks";
import { GetProp } from "antd";
import { FormInstance } from "antd/es/form";
import { get, isBoolean, isEmpty, isEqual, isNil, omit, trim } from "lodash-es";
import { useEffect } from "react";
import { ButtonState, names, websiteBuildModeForcedOffMcpIds } from "./constant";
import { getAttachmentBlocks } from "./util";

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
  const hasReady = getAttachmentBlocks(attachmentItems).length === attachmentItems.length;
  if (hasReady) {
    return ButtonState.Typing;
  }

  return ButtonState.WaitingType;
}

const defaultFormValue: ChatInputConfig = {
  thinkMode: false,
  websiteBuildMode: false,
  mcpAutoMode: true,
  sourceConfig: {},
  modelID: "default",
};

// 创建 memoized selector 来避免不必要的重新渲染
const selectMCPConfig = createSelector(
  [(state: RootState) => state.mcp.mcpConfig, (state: RootState) => state.mcp.mcpConfigLoaded],
  (mcpConfig, mcpConfigLoaded) => ({ mcpConfig, mcpConfigLoaded })
);
const selectModels = createSelector(
  [(state: RootState) => state.models.models, (state: RootState) => state.models.loaded],
  (models, modelsLoaded) => ({ models, modelsLoaded })
);
export const chatInputFormValuesStorageKey = "chat-input-form-values-v1";

export function useFormValuesChange(form: FormInstance<ChatInputFormValues>) {
  const [formValues, setFormValues] = useLocalStorageState<ChatInputConfig>(chatInputFormValuesStorageKey, {
    defaultValue: defaultFormValue,
  });
  const { mcpConfig, mcpConfigLoaded } = useAppSelector(selectMCPConfig);
  const { models, modelsLoaded } = useAppSelector(selectModels);

  useEffect(() => {
    if (mcpConfigLoaded) {
      setFormValues(pre => {
        const websiteBuildMode = isBoolean(pre?.websiteBuildMode) ? pre?.websiteBuildMode : false;
        let mcpAutoMode = isBoolean(pre?.mcpAutoMode) ? pre?.mcpAutoMode : true;
        const sourceConfig = mcpConfig.reduce((acc: RetrieverSource, item) => {
          const preState = get(pre, ["sourceConfig", item.id], undefined);
          // 如果之前没有选中，或者当前 MCP 不在线，则使用服务端默认值
          if (isNil(preState) || !item.online) {
            acc[item.id] = item.online;
          } else {
            acc[item.id] = preState;
          }
          return acc;
        }, {} as RetrieverSource);
        if (websiteBuildMode) {
          mcpAutoMode = false;
          for (const id of websiteBuildModeForcedOffMcpIds) {
            sourceConfig[id] = false;
          }
        }
        return {
          ...pre,
          websiteBuildMode,
          mcpAutoMode,
          sourceConfig,
        } as ChatInputConfig;
      });
    }
  }, [mcpConfigLoaded, mcpConfig, setFormValues]);

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
        if (Object.prototype.hasOwnProperty.call(_changedFields, "websiteBuildMode")) {
          if (_changedFields.websiteBuildMode === true) {
            const nextSource = { ...base.sourceConfig };
            for (const id of websiteBuildModeForcedOffMcpIds) {
              nextSource[id] = false;
            }
            return {
              ...base,
              mcpAutoMode: false,
              sourceConfig: nextSource,
            };
          }
          if (_changedFields.websiteBuildMode === false) {
            return { ...base, mcpAutoMode: true };
          }
        }
        return base;
      });
    }
  );

  useEffect(() => {
    form.setFieldsValue(formValues);
  }, [formValues, form]);

  return {
    values: formValues,
    onValuesChange,
  };
}

export const cachedMcpConfigStorageKey = "cached-mcp-config-v1";
const defaultCachedMcpConfig: MCPConfigItem[] = [];

export function useMCPConfig() {
  const { mcpConfig, mcpConfigLoaded } = useAppSelector(selectMCPConfig);
  const [cachedMcpConfig, setCachedMcpConfig] = useLocalStorageState<MCPConfigItem[]>(cachedMcpConfigStorageKey, {
    defaultValue: defaultCachedMcpConfig,
  });

  useEffect(() => {
    if (mcpConfigLoaded) {
      setCachedMcpConfig(mcpConfig);
    }
  }, [mcpConfigLoaded, mcpConfig, setCachedMcpConfig]);

  return cachedMcpConfig || defaultCachedMcpConfig;
}

export function useModelImageSupport(modelId: string | undefined): boolean {
  const models = useAppSelector((state: RootState) => state.models.models);
  const selectedModel = models.find(item => item.modelId === modelId);
  return selectedModel?.imageSupport ?? true;
}
