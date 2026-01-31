import {
  TOKEN_STATS_AGENT_NAMES_SORTED,
  TOKEN_STATS_TITLE_BY_AGENT_NAME,
} from "@/constants";
import { TokenStats, TotalTokenStats } from "@/interfaces/token";
import { useMemo } from "react";

export function useTokenStatsDisplay(tokenStats: TotalTokenStats | undefined) {
  return useMemo(() => {
    const result: { title: string; value: TokenStats; index: number }[] = [];
    for (const value of Object.values(tokenStats || {}) as TokenStats[]) {
      if (!value) {
        continue;
      }

      const title = TOKEN_STATS_TITLE_BY_AGENT_NAME[value.agentName];
      result.push({
        title,
        value,
        index: TOKEN_STATS_AGENT_NAMES_SORTED.indexOf(value.agentName),
      });
    }

    result.sort((a, b) => a.index - b.index);
    const titles = result.map(item => item.title);
    const tokenStatsList = result.map(item => item.value);
    return { titles, tokenStats: tokenStatsList };
  }, [tokenStats]);
}
