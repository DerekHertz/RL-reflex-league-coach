import { ButtonHTMLAttributes, ReactNode } from "react";
import { PulseDot } from "./PulseDot";
import styles from "./Button.module.css";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  variant?: "primary" | "secondary";
  /** "paper" (default) reads on the parchment surface; "ink" swaps the
   * secondary/outline colors to the on-ink family so the button stays
   * legible on an ink-chrome surface (e.g. the error panel). */
  tone?: "paper" | "ink";
  busy?: boolean;
  /** Present-participle label shown while busy, e.g. "Reading…". Defaults to children. */
  busyLabel?: ReactNode;
  children: ReactNode;
}

/** Both the resting and busy labels render in the same grid cell (one
 * visibility:hidden) so the button's width is the max of the two and never
 * changes when the busy state toggles. */
export function Button({
  variant = "primary",
  tone = "paper",
  busy = false,
  busyLabel,
  children,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  const variantClass =
    variant === "primary" ? styles.primary : tone === "ink" ? styles.secondaryInk : styles.secondary;
  return (
    <button
      className={`${styles.btn} ${variantClass} ${className ?? ""}`}
      disabled={disabled || busy}
      {...rest}
    >
      <span className={styles.stack}>
        <span className={`type-ui ${styles.slot} ${busy ? styles.invisible : ""}`}>{children}</span>
        <span className={`type-ui ${styles.slot} ${busy ? "" : styles.invisible}`}>
          <PulseDot /> {busyLabel ?? children}
        </span>
      </span>
    </button>
  );
}
