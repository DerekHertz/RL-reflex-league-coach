import { PulseDot } from "./PulseDot";
import { useSession } from "@/lib/session";
import styles from "./AnalysisProgress.module.css";

/** Shown on pages other than "/" while a shared analysis job (kicked off
 * from any page) is still running -- reads directly from SessionContext
 * rather than taking props, so any page can drop this in as-is. */
export function AnalysisProgress() {
  const { analysis } = useSession();
  if (analysis.status !== "loading") return null;

  return (
    <p className={`type-ui ${styles.line}`}>
      <PulseDot />
      <span>Analyzing your last match first -- {analysis.message || "starting..."}</span>
    </p>
  );
}
