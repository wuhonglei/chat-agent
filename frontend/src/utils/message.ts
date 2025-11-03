import { MessageInstance } from "antd/es/message/interface";
import { message } from "antd";

// 创建一个全局的 message 实例存储
let messageInstance: MessageInstance | null = null;

export const setMessageInstance = (instance: MessageInstance) => {
  messageInstance = instance;
};

export const getMessageInstance = (): MessageInstance => {
  if (!messageInstance) {
    // 如果还没有初始化，降级使用静态方法
    // 这不应该发生，但作为后备方案
    return message as MessageInstance;
  }
  return messageInstance;
};
