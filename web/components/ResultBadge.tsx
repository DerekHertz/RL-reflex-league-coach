import { resultLabel } from "@/lib/presentation";
import styles from "./ResultBadge.module.css";

export function ResultBadge({ result }: { result: "win" | "loss" }) {
  const label = resultLabel(result);
  return (
    <span className={`${styles.badge} ${result === "win" ? styles.victory : styles.defeat}`}>
      {label}
    </span>
  );
}
