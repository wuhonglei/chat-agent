import { Form, Select, Typography } from "antd";
import { SizeType } from "antd/es/config-provider/SizeContext";
import { isEmpty } from "lodash-es";
import React from "react";
import { ModelOption, useModelOptions } from "./hooks";
import { names } from "../constant";

interface Props {
  size: SizeType;
  hasImageContext: boolean;
}

const ModelSelect: React.FC<Props> = ({ size, hasImageContext }) => {
  const options = useModelOptions(hasImageContext);

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
        getPopupContainer={() => document.body}
        optionRender={option => {
          const data = option.data as ModelOption;
          return (
            <div className="py-1">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs text-black-primary leading-5 truncate">{String(data.label)}</div>
                <div className="flex items-center gap-1.5 text-black-secondary">
                  {data.supportItems
                    .filter(({ supported }) => supported)
                    .map(({ key, label, icon: Icon }) => (
                      <span key={key} title={label} className="inline-flex">
                        <Icon className="text-black-secondary" />
                      </span>
                    ))}
                </div>
              </div>
              <Typography.Paragraph
                ellipsis={{ rows: 2 }}
                className="leading-5"
                title={data.description}
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
