import { useEffect } from "react";
import { FormInstance } from "antd/es/form";
import { ButtonState, names } from "./constant";
import { trim, omit, isEqual, get, isNil, isBoolean } from "lodash-es";
import { ChatInputFormValues, RetrieverSource } from "@/interfaces";
import { useLocalStorageState, useMemoizedFn } from "ahooks";
import { useAppSelector } from "@/store/hooks";
import { createSelector } from "@reduxjs/toolkit";
import { RootState } from "@/store";

/**
 * 根据消息内容和是否流式传输，返回按钮状态
 * @param message
 * @param isStreaming 是否流式传输
 * @returns 按钮状态
 */
export function useButtonState(
  message: string,
  isStreaming: boolean
): ButtonState {
  if (isStreaming) {
    return ButtonState.Streaming;
  }

  if (trim(message)) {
    return ButtonState.Typing;
  }

  return ButtonState.WaitingType;
}

const defaultFormValue: Omit<ChatInputFormValues, "message"> = {
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

export function useFormValuesChange(form: FormInstance<ChatInputFormValues>) {
  const [formValues, setFormValues] = useLocalStorageState<
    Omit<ChatInputFormValues, "message">
  >("chat-input-form-values-v1", {
    defaultValue: defaultFormValue,
  });
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
          }) as Omit<ChatInputFormValues, "message">
      );
    }
  }, [mcpConfigLoaded, mcpConfig, setFormValues]);

  const onValuesChange = useMemoizedFn(
    (
      _changedFields: Partial<ChatInputFormValues>,
      allFields: ChatInputFormValues
    ) => {
      const changedKeys = Object.keys(_changedFields);
      if (isEqual(changedKeys, names.message)) {
        return;
      }
      setFormValues(omit(allFields, "message"));
    }
  );

  useEffect(() => {
    form.setFieldsValue(formValues);
  }, [formValues, form]);

  return {
    onValuesChange,
  };
}
