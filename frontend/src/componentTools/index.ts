import { ComponentToolItem } from "@/interfaces";

const componentTools: ComponentToolItem[] = [
  {
    name: "weather",
    whenCondition: "and",
    when: {
      mcp_tool_names: ["weather"],
    },
  },
];

export default componentTools;
