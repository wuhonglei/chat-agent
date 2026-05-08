import { useAppSelector } from "@/store/hooks";
import { Form, Select } from "antd";
import { SizeType } from "antd/es/config-provider/SizeContext";
import { DefaultOptionType } from "antd/es/select";
import { isEmpty } from "lodash-es";
import React from "react";
import { names } from "../constant";

interface Props {
  size: SizeType;
  hasImageAttachment: boolean;
}

const ModelSelect: React.FC<Props> = ({ size, hasImageAttachment }) => {
  const { models } = useAppSelector(state => state.models);
  const options: DefaultOptionType[] = models.map(item => ({
    value: item.modelId,
    label: (item.title && item.title.trim()) || item.modelId,
    disabled: hasImageAttachment && !item.imageSupport,
  }));

  return (
    <Form.Item name={names.modelId}>
      <Select size={size} options={options} disabled={isEmpty(options)} variant="borderless" />
    </Form.Item>
  );
};

export default React.memo(ModelSelect);
