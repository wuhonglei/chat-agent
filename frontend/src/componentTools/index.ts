import { ComponentToolItem } from "@/interfaces";
import WeatherNow from "./components/WeatherNow";

const componentTools: ComponentToolItem[] = [
  {
    name: "weather",
    component: WeatherNow,
    typeSourceFile: "./components/WeatherNow/type.ts",
    whenCondition: "and",
    when: {
      mcp_tool_names: ["weather"],
    },
  },
];

export default componentTools;
