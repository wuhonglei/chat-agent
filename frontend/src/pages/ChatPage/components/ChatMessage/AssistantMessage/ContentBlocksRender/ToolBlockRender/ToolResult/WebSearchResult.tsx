import type { WebSearchDisplayItem } from "@/interfaces/contentBlock";
import { isEmpty } from "lodash-es";
import React from "react";

function getHostname(url?: string): string {
  if (!url) {
    return "";
  }
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export type WebSearchResultProps = {
  items: WebSearchDisplayItem[];
};

function renderResultItem(item: WebSearchDisplayItem["results"][number], key: string): React.ReactNode {
  const content = (
    <>
      <div className="flex-1 flex items-center gap-2">
        {item.favicon ? (
          <img alt="" src={item.favicon} className="mt-0.5 h-3 w-3 shrink-0 rounded-sm" />
        ) : (
          <div className="mt-0.5 h-3 w-3 shrink-0 rounded-sm bg-black/10" />
        )}
        <div className="flex-1 w-0 truncate text-black/65" title={item.title || item.url || "Untitled result"}>
          {item.title || item.url || "Untitled result"}
        </div>
      </div>
      <div className="truncate text-black/45">{getHostname(item.url)}</div>
    </>
  );

  const className =
    "flex w-full justify-between gap-3 px-2 py-1.5 text-left text-xs transition-colors hover:bg-black/4!";

  if (item.url) {
    return (
      <a key={key} href={item.url} target="_blank" rel="noreferrer" className={className}>
        {content}
      </a>
    );
  }

  return (
    <div key={key} className={className}>
      {content}
    </div>
  );
}

const WebSearchResult: React.FC<WebSearchResultProps> = ({ items }) => {
  if (isEmpty(items)) {
    return null;
  }

  return (
    <div className="flex w-full flex-col gap-3">
      {items.map((item, groupIndex) => {
        const results = item.results || [];
        const queryTitle = item.query || "Search results";

        return (
          <div
            key={`${item.query || "web-search-query"}_${groupIndex}`}
            className="w-full overflow-hidden rounded-xl border border-black/6 bg-black/2"
          >
            <div className="flex items-center justify-between gap-3 px-2 py-2 text-sm">
              <div className="min-w-0 truncate text-black/88">{queryTitle}</div>
              <span className="shrink-0 text-black/45">{results.length} results</span>
            </div>
            {results.length ? (
              <div className="max-h-[320px] overflow-auto bg-white flex flex-col gap-1">
                {results.map((result, resultIndex) =>
                  renderResultItem(
                    result,
                    `${result.url || result.title || "web-search-item"}_${groupIndex}_${resultIndex}`
                  )
                )}
              </div>
            ) : (
              <div className="border-t border-black/6 px-4 py-3 text-sm text-black/45">No results</div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default React.memo(WebSearchResult);
