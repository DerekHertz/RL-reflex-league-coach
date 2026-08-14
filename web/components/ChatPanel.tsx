"use client";

import { useState } from "react";
import { ApiError, ChatTurn, CoachingResponse, MatchFactSheet, postChatMessage } from "@/lib/api";
import { Button } from "./Button";
import styles from "./ChatPanel.module.css";

export function ChatPanel({ sheet, narrative }: { sheet: MatchFactSheet; narrative: CoachingResponse }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || pending) return;

    setPending(true);
    setError(null);
    try {
      const result = await postChatMessage(sheet, narrative, trimmed, history);
      setHistory((prev) => [...prev, { question: trimmed, answer: result.answer }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className={styles.panel}>
      <p className={`type-eyebrow ${styles.eyebrow}`}>Ask about this match</p>

      {history.length > 0 && (
        <ul className={styles.turns}>
          {history.map((turn, i) => (
            <li key={i} className={styles.turn}>
              <p className={`type-ui ${styles.question}`}>{turn.question}</p>
              <p className={`type-body ${styles.answer}`}>{turn.answer}</p>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className={styles.form}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Why did the ward drought check flag me?"
          disabled={pending}
          className={styles.input}
        />
        <Button type="submit" disabled={pending || !question.trim()} busy={pending} busyLabel="Asking…">
          Ask
        </Button>
      </form>

      {error && <p className={`type-body-s ${styles.error}`}>{error}</p>}
    </section>
  );
}
