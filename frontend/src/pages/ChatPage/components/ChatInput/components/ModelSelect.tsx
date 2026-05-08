import { useAppSelector } from "@/store/hooks";
import { Form, Select, Typography } from "antd";
import { SizeType } from "antd/es/config-provider/SizeContext";
import { DefaultOptionType } from "antd/es/select";
import { isEmpty } from "lodash-es";
import React from "react";
import { names } from "../constant";

interface Props {
  size: SizeType;
  hasImageContext: boolean;
}

interface ModelOption extends DefaultOptionType {
  description: string;
}

const ModelSelect: React.FC<Props> = ({ size, hasImageContext }) => {
  const { models } = useAppSelector(state => state.models);
  const options: ModelOption[] = models.map(item => ({
    value: item.modelId,
    label: (item.title && item.title.trim()) || item.modelId,
    description: (item.description && item.description.trim()) || item.modelId,
    disabled: hasImageContext && !item.imageSupport,
  }));

  return (
    <Form.Item name={names.modelId}>
      <Select
        size={size}
        options={options}
        variant="borderless"
        disabled={isEmpty(options)}
        styles={{
          popup: { root: { width: 274 } },
          content: { fontSize: 12, color: "var(--color-black-secondary)" },
        }}
        optionRender={option => {
          const data = option.data as ModelOption;
          return (
            <div className="py-1">
              <div className="text-xs text-black-primary leading-5 truncate">{String(data.label)}</div>
              <Typography.Paragraph
                ellipsis={{ rows: 2 }}
                className="leading-5"
                style={{ marginBottom: 0, whiteSpace: "normal", fontSize: 12, color: "var(--color-black-secondary)" }}
              >
                {data.description}
              </Typography.Paragraph>
            </div>
          );
        }}
      />
    </Form.Item>
  );
};

export default React.memo(ModelSelect);
