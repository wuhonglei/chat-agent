import mermaid from "mermaid";
import { useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";

type Props = {
  code: string;
  style?: React.CSSProperties;
};

// 初始化 Mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "loose",
});

export default function MermaidBlock({ code, style }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const idRef = useRef<string>(`mermaid-${uuidv4()}`);

  useEffect(() => {
    mermaid
      .render(idRef.current, code)
      .then(result => {
        if (ref.current) {
          ref.current.innerHTML = result.svg;
        }
      })
      .catch(error => {
        console.error("Mermaid rendering error:", error);
        if (ref.current) {
          ref.current.innerHTML = `<pre>${code}</pre>`;
        }
      });
  }, [code]);

  return <div ref={ref} className="mermaid" style={style} />;
}
