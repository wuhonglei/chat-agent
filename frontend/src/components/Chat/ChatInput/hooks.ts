import { ButtonState } from "./constant";
import { trim } from "lodash-es";

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
