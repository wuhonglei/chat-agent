import mermaid from "mermaid";
import { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import GrayContainer, { CopyButton } from "./GrayContainer";
import { Segmented } from "antd";
import NormalCode from "./NormalCode";
import classNames from "classnames";
import { useSize } from "ahooks";

type Props = {
  code: string;
  style?: React.CSSProperties;
};

// 初始化 Mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "loose",
  suppressErrorRendering: true,
});

const options = [
  {
    label: "预览",
    value: "svg",
  },
  {
    label: "代码",
    value: "code",
  },
];

export default function MermaidBlock({ code, style }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const idRef = useRef<string>(`mermaid-${uuidv4()}`);
  const [activeKey, setActiveKey] = useState<string>(options[0].value);

  useEffect(() => {
    mermaid
      .render(idRef.current, code)
      .then(result => {
        if (ref.current) {
          ref.current.innerHTML = result.svg;
        }
      })
      .catch(error => {
        // console.warn(error);
      });
  }, [code]);

  return (
    <GrayContainer
      header={
        <>
          <Segmented
            shape="round"
            options={options}
            value={activeKey}
            onChange={setActiveKey}
          />
          <CopyButton children={code} />
        </>
      }
    >
      <div
        ref={ref}
        style={{ ...style }}
        className={classNames(
          "mermaid mx-auto min-h-[300px]",
          activeKey !== "svg" && "hidden"
        )}
      />
      <NormalCode
        language="mermaid"
        style={activeKey !== "code" ? { display: "none" } : {}}
      >
        {code}
      </NormalCode>
    </GrayContainer>
  );
}
