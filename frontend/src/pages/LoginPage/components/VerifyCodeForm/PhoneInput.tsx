import { MobileOutlined } from "@ant-design/icons";
import { Input, Space } from "antd";
import React from "react";

interface PhoneInputProps {
  value?: string;
  onChange?: (value: string) => void;
}

const PhoneInput: React.FC<PhoneInputProps> = ({ value, onChange }) => (
  <Space.Compact className="w-full">
    <Space.Addon className="w-16">+86</Space.Addon>
    <Input
      prefix={<MobileOutlined style={{ color: "var(--color-black-quaternary)" }} />}
      className="flex-1"
      placeholder="请输入手机号"
      size="large"
      value={value}
      onChange={e => onChange?.(e.target.value)}
    />
  </Space.Compact>
);

export default PhoneInput;
