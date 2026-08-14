import { Severity, severityLabel } from "@/lib/presentation";
import styles from "./SeverityBadge.module.css";

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const label = severityLabel(severity);
  const variant =
    label === "MAJOR" ? styles.major : label === "MODERATE" ? styles.moderate : styles.minor;
  return <span className={`${styles.badge} ${variant}`}>{label}</span>;
}
