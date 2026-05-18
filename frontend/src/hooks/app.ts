import { WEB_TAB_TITLE } from "@/constants";
import { ConversationInfo } from "@/interfaces";
import { useAppDispatch } from "@/store/hooks";
import { fetchModels } from "@/store/slices/modelsSlice";
import { getUserDetail } from "@/store/slices/userSlice";
import { isTitleCreatedByDefault } from "@/utils";
import { setMessageInstance } from "@/utils/message";
import { useTitle } from "ahooks";
import { App as AntdApp } from "antd";
import { isEmpty } from "lodash-es";
import { useEffect, useMemo } from "react";

/**
 * 应用初始化：拉取用户详情与模型列表
 */
export function useAppInit(): void {
  const dispatch = useAppDispatch();

  useEffect(() => {
    const init = async () => {
      try {
        dispatch(fetchModels());
        await dispatch(getUserDetail()).unwrap();
      } catch (error) {
        console.error("初始化失败", error);
      }
    };
    init();
  }, [dispatch]);
}

/**
 * 初始化 Ant Design message 实例，供全局使用
 */
export function useMessageInstance(): void {
  const { message } = AntdApp.useApp();

  useEffect(() => {
    setMessageInstance(message);
  }, [message]);
}

export function useWebTitle(conversationInfo: ConversationInfo | undefined | null): void {
  const title = useMemo(() => {
    if (isEmpty(conversationInfo)) {
      return WEB_TAB_TITLE;
    } else if (isTitleCreatedByDefault(conversationInfo.createdBy)) {
      return WEB_TAB_TITLE;
    } else {
      return conversationInfo.title;
    }
  }, [conversationInfo]);

  useTitle(title);
}
