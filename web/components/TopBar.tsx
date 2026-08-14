"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./TopBar.module.css";

const NAV_ITEMS: { label: string; href: string | null }[] = [
  { label: "Last match", href: "/" },
  { label: "Champions", href: "/champions" },
  { label: "Ledger", href: "/ledger" },
  { label: "Your pool", href: "/pool" },
  { label: "Coach", href: null },
];

export function TopBar() {
  const pathname = usePathname();
  return (
    <header className={styles.bar}>
      <span className={`type-eyebrow ${styles.wordmark}`}>LOLCOACH</span>
      <nav className={styles.nav} aria-label="Primary">
        {NAV_ITEMS.map((item) => {
          if (!item.href) {
            return (
              <span
                key={item.label}
                className={`type-ui ${styles.navItem} ${styles.inert}`}
                aria-disabled="true"
              >
                {item.label}
              </span>
            );
          }
          const active = item.href === pathname;
          return (
            <Link
              key={item.label}
              href={item.href}
              className={`type-ui ${styles.navItem} ${active ? styles.active : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
