import { useIsSmallScreen } from "@/hooks";
import { ChatMessage } from "@/interfaces";
import { getMessageTextFromBlocks } from "@/interfaces/contentBlock";
import { useMemoizedFn, useThrottleFn } from "ahooks";
import classNames from "classnames";
import { truncate } from "lodash-es";
import React, { useEffect, useMemo, useState } from "react";
import styles from "./index.module.css";

const USER_MESSAGE_ID_PREFIX = "user-message-";
const ACTIVE_OFFSET_PX = 80;
const SCROLL_TOP_PADDING = 12;
const SUMMARY_LENGTH = 20;
const MIN_USER_MESSAGES = 2;

type QuestionItem = {
  id: string;
  summary: string;
};

type Props = {
  messages: ChatMessage[];
  containerRef: React.RefObject<HTMLElement | null>;
};

function buildSummary(message: ChatMessage): string {
  const text = getMessageTextFromBlocks(message.contentBlocks).replace(/\s+/g, " ").trim();
  if (!text) {
    return "附件";
  }
  return truncate(text, { length: SUMMARY_LENGTH, omission: "…" });
}

function getUserMessageElement(messageId: string): HTMLElement | null {
  return document.getElementById(`${USER_MESSAGE_ID_PREFIX}${messageId}`);
}

/** Element top relative to the scroll container's content origin. */
function getOffsetTopInContainer(container: HTMLElement, el: HTMLElement): number {
  const containerRect = container.getBoundingClientRect();
  const elRect = el.getBoundingClientRect();
  return elRect.top - containerRect.top + container.scrollTop;
}

const QuestionTimeline: React.FC<Props> = ({ messages, containerRef }) => {
  const isSmallScreen = useIsSmallScreen();
  const [activeId, setActiveId] = useState<string | null>(null);

  const questions = useMemo<QuestionItem[]>(() => {
    return messages
      .filter(message => message.role === "user")
      .map(message => ({
        id: message.id,
        summary: buildSummary(message),
      }));
  }, [messages]);

  const updateActiveQuestion = useMemoizedFn(() => {
    const container = containerRef.current;
    if (!container || questions.length === 0) {
      setActiveId(null);
      return;
    }

    const threshold = container.scrollTop + ACTIVE_OFFSET_PX;
    let nextActiveId: string | null = questions[0]?.id ?? null;

    for (const question of questions) {
      const el = getUserMessageElement(question.id);
      if (!el) continue;
      const top = getOffsetTopInContainer(container, el);
      if (top <= threshold) {
        nextActiveId = question.id;
      } else {
        break;
      }
    }

    setActiveId(nextActiveId);
  });

  const { run: onScrollThrottled } = useThrottleFn(updateActiveQuestion, { wait: 100 });

  useEffect(() => {
    const container = containerRef.current;
    if (!container || questions.length < MIN_USER_MESSAGES) return;

    updateActiveQuestion();
    container.addEventListener("scroll", onScrollThrottled, { passive: true });
    return () => {
      container.removeEventListener("scroll", onScrollThrottled);
    };
  }, [containerRef, onScrollThrottled, questions, updateActiveQuestion]);

  const handleJump = useMemoizedFn((messageId: string) => {
    const container = containerRef.current;
    const el = getUserMessageElement(messageId);
    if (!container || !el) return;

    const top = getOffsetTopInContainer(container, el);
    container.scrollTo({
      top: Math.max(0, top - SCROLL_TOP_PADDING),
      behavior: "smooth",
    });
    setActiveId(messageId);
  });

  if (isSmallScreen || questions.length < MIN_USER_MESSAGES) {
    return null;
  }

  return (
    <nav className={styles.rail} aria-label="问题导航">
      <div className={styles.list}>
        {questions.map(question => {
          const isActive = question.id === activeId;
          return (
            <button
              key={question.id}
              type="button"
              className={classNames(styles.item, isActive && styles.itemActive)}
              onClick={() => handleJump(question.id)}
              title={question.summary}
              aria-current={isActive ? "true" : undefined}
            >
              <span className={styles.label}>{question.summary}</span>
              <span className={styles.tick} aria-hidden />
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default React.memo(QuestionTimeline);
