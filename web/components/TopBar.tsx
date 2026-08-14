import styles from "./TopBar.module.css";

const INERT_NAV_ITEMS = ["Ledger", "Champions", "Coach"];

export function TopBar() {
  return (
    <header className={styles.bar}>
      <span className={`type-eyebrow ${styles.wordmark}`}>LOLCOACH</span>
      <nav className={styles.nav} aria-label="Primary">
        <span className={`type-ui ${styles.navItem} ${styles.active}`} aria-current="page">
          Last match
        </span>
        {INERT_NAV_ITEMS.map((item) => (
          <span key={item} className={`type-ui ${styles.navItem} ${styles.inert}`} aria-disabled="true">
            {item}
          </span>
        ))}
      </nav>
    </header>
  );
}
