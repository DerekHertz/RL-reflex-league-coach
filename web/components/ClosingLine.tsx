import styles from "./ClosingLine.module.css";

export function ClosingLine({ text }: { text: string }) {
  return (
    <blockquote className={styles.closing}>
      <p className="type-quote-closing">{text}</p>
    </blockquote>
  );
}
