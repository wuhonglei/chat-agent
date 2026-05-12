import ImageSupportIcon from "@/assets/svg/models/ImageSupport.svg?react";
import TextSupportIcon from "@/assets/svg/models/TextSupport.svg?react";
import VideoSupportIcon from "@/assets/svg/models/VideoSupport.svg?react";
import VoiceSupportIcon from "@/assets/svg/models/VoiceSupport.svg?react";
import { useAppSelector } from "@/store/hooks";
import { DefaultOptionType } from "antd/es/select";
import React from "react";

export interface ModelOption extends DefaultOptionType {
  description: string;
  supportItems: {
    key: string;
    label: string;
    icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
    supported: boolean;
  }[];
}

const getModelSupportValue = (item: unknown, key: string): boolean => {
  if (!item || typeof item !== "object") {
    return false;
  }
  return Boolean((item as Record<string, unknown>)[key]);
};

export const useModelOptions = (hasImageContext: boolean): ModelOption[] => {
  const { models } = useAppSelector(state => state.models);

  return React.useMemo(
    () =>
      models.map(item => ({
        value: item.modelId,
        label: (item.title && item.title.trim()) || item.modelId,
        description: (item.description && item.description.trim()) || item.modelId,
        disabled: hasImageContext && !item.imageSupport,
        supportItems: [
          { key: "text", label: "文本", icon: TextSupportIcon, supported: true },
          { key: "image", label: "图片", icon: ImageSupportIcon, supported: item.imageSupport },
          {
            key: "video",
            label: "视频",
            icon: VideoSupportIcon,
            supported: getModelSupportValue(item as unknown, "videoSupport"),
          },
          {
            key: "voice",
            label: "语音",
            icon: VoiceSupportIcon,
            supported: getModelSupportValue(item as unknown, "voiceSupport"),
          },
        ],
      })),
    [hasImageContext, models]
  );
};
