import { ComponentToolItem } from "@/interfaces";
import { lazy } from "react";

const componentTools: ComponentToolItem[] = [
  {
    name: "weather",
    component: lazy(() => import("./components/WeatherNow")),
    typeSourceFile: "./components/WeatherNow/type.ts",
    whenCondition: "and",
    when: {
      tool_names: ["weather"],
    },
  },
];

export default componentTools;
