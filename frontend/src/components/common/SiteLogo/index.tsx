import { Avatar } from "antd";
import { WEB_LOGO } from "@/constants";

type Props = {
  size?: number;
  bgColor?: string;
};

export default function SiteLogo({ size = 36, bgColor = "#D0E3FD" }: Props) {
  return (
    <Avatar
      size={size}
      src={WEB_LOGO}
      className="shadow-2xs"
      style={{ backgroundColor: bgColor, border: "none" }}
    >
      LOGO
    </Avatar>
  );
}
