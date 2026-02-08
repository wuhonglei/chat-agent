import { ComponentToolItem } from "@/interfaces";
import type { ComponentType } from "react";
import WeatherNow from "./components/WeatherNow";

const componentTools: ComponentToolItem[] = [
  {
    name: "weather",
    component: WeatherNow as unknown as ComponentType<Record<string, unknown>>,
    typeSourceFile: "./components/WeatherNow/type.ts",
    whenCondition: "and",
    when: {
      mcp_tool_names: ["weather"],
    },
  },
];

export default componentTools;
