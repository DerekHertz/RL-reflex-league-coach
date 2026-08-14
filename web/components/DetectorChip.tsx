import { severityColorVar } from "@/lib/presentation";
import styles from "./DetectorChip.module.css";

/** Shows a finding's raw id verbatim (e.g. "unspent_gold:0") -- never
 * prettified. Static in v1: no scroll-to-finding interaction yet. */
export function DetectorChip({ id, severity }: { id: string; severity: string }) {
  const color = severityColorVar(severity);
  return (
    <span
      className={styles.chip}
      style={
        {
          "--chip-color": color,
        } as React.CSSProperties
      }
    >
      {id}
    </span>
  );
}
