import { useEffect } from "react";
import { FormInstance } from "antd/es/form";
import { ButtonState, names } from "./constant";
import { trim, omit, isEqual, get, isNil, isBoolean } from "lodash-es";
import {
  ChatInputFormValues,
  ChatInputConfig,
  MCPConfigItem,
  RetrieverSource,
} from "@/interfaces";
import { useLocalStorageState, useMemoizedFn } from "ahooks";
import { useAppSelector } from "@/store/hooks";
import { createSelector } from "@reduxjs/toolkit";
import { RootState } from "@/store";

/**
 * 根据消息内容和是否流式传输，返回按钮状态
 * @param content
 * @param isStreaming 是否流式传输
 * @returns 按钮状态
 */
export function useButtonState(
  content: string,
  isStreaming?: boolean
): ButtonState {
  if (isStreaming) {
    return ButtonState.Streaming;
  }

  if (trim(content)) {
    return ButtonState.Typing;
  }

  return ButtonState.WaitingType;
}

const defaultFormValue: ChatInputConfig = {
  thinkMode: false,
  mcpAutoMode: true,
  sourceConfig: {},
};

// 创建 memoized selector 来避免不必要的重新渲染
const selectMCPConfig = createSelector(
  [
    (state: RootState) => state.global.mcpConfig,
    (state: RootState) => state.global.mcpConfigLoaded,
  ],
  (mcpConfig, mcpConfigLoaded) => ({ mcpConfig, mcpConfigLoaded })
);
export const chatInputFormValuesStorageKey = "chat-input-form-values-v1";

export function useFormValuesChange(form: FormInstance<ChatInputFormValues>) {
  const [formValues, setFormValues] = useLocalStorageState<ChatInputConfig>(
    chatInputFormValuesStorageKey,
    {
      defaultValue: defaultFormValue,
    }
  );
  const { mcpConfig, mcpConfigLoaded } = useAppSelector(selectMCPConfig);

  useEffect(() => {
    if (mcpConfigLoaded) {
      setFormValues(
        pre =>
          ({
            ...pre,
            mcpAutoMode: isBoolean(pre?.mcpAutoMode) ? pre?.mcpAutoMode : true,
            sourceConfig: mcpConfig.reduce((acc: RetrieverSource, item) => {
              const preState = get(pre, ["sourceConfig", item.id], undefined);
              // 如果之前没有选中，或者当前 MCP 不在线，则使用服务端默认值
              if (isNil(preState) || !item.online) {
                acc[item.id] = item.online;
              } else {
                acc[item.id] = preState;
              }
              return acc;
            }, {} as RetrieverSource),
          }) as ChatInputConfig
      );
    }
  }, [mcpConfigLoaded, mcpConfig, setFormValues]);

  const onValuesChange = useMemoizedFn(
    (
      _changedFields: Partial<ChatInputFormValues>,
      allFields: ChatInputFormValues
    ) => {
      const changedKeys = Object.keys(_changedFields);
      if (isEqual(changedKeys, names.content)) {
        return;
      }
      setFormValues(pre => ({
        ...pre,
        ...omit(allFields, "content"),
      }));
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
  const [cachedMcpConfig, setCachedMcpConfig] = useLocalStorageState<
    MCPConfigItem[]
  >(cachedMcpConfigStorageKey, {
    defaultValue: defaultCachedMcpConfig,
  });

  useEffect(() => {
    if (mcpConfigLoaded) {
      setCachedMcpConfig(mcpConfig);
    }
  }, [mcpConfigLoaded, mcpConfig, setCachedMcpConfig]);

  return cachedMcpConfig || defaultCachedMcpConfig;
}
