import { ButtonState } from "./constant";

export function isButtonDisabled(buttonState: ButtonState) {
  return buttonState === ButtonState.WaitingType;
}

export function isStreamingState(buttonState: ButtonState) {
  return buttonState === ButtonState.Streaming;
}
