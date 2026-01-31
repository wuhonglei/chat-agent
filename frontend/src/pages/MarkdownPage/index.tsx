import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { Tabs } from "antd";
import classNames from "classnames";
import React, { useState } from "react";
import styles from "./index.module.css";
import code from "./raw/code.md?raw";
import mermaid from "./raw/mermaid.md?raw";
import reactMarkdown from "./raw/react-markdown.md?raw";
import simplify from "./raw/simplify.md?raw";
import weather from "./raw/weather.md?raw";

const items = [
  {
    key: "1",
    label: "Simplify",
  },
  {
    key: "2",
    label: "React Markdown",
  },
  {
    key: "3",
    label: "Mermaid",
  },
  {
    key: "4",
    label: "Code",
  },
  {
    key: "5",
    label: "Weather",
  },
];

const content = {
  [items[0]?.key]: simplify,
  [items[1]?.key]: reactMarkdown,
  [items[2]?.key]: mermaid,
  [items[3]?.key]: code,
  [items[4]?.key]: weather,
};

const MarkdownPage = () => {
  const [activeKey, setActiveKey] = useState(items[0].key);
  const code = content[activeKey];
  console.info("code", code);

  return (
    <div className="flex flex-col h-full">
      <Tabs
        items={items}
        activeKey={activeKey}
        tabBarStyle={{ marginBottom: 0 }}
        onChange={key => setActiveKey(key)}
        style={{ paddingLeft: "32px" }}
      />
      <MarkdownContainer className={classNames(styles.container, "flex-1 text-base")}>{code}</MarkdownContainer>
    </div>
  );
};

export default React.memo(MarkdownPage);
