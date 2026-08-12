import { AnalysisResult } from "@/lib/api";

const SEVERITY_COLOR: Record<string, string> = {
  major: "#b91c1c",
  moderate: "#c2410c",
  minor: "#a16207",
  info: "#555",
};

export function ResultView({ result }: { result: AnalysisResult }) {
  const { fact_sheet: sheet, narrative } = result;

  return (
    <section style={{ marginTop: 32 }}>
      <h2>
        {sheet.subject.champion} ({sheet.subject.role}) &mdash;{" "}
        <span
          style={{ color: sheet.match.result === "win" ? "#15803d" : "#b91c1c" }}
        >
          {sheet.match.result.toUpperCase()}
        </span>{" "}
        {sheet.match.duration}
      </h2>
      <p style={{ color: "#666", fontSize: 14 }}>
        {sheet.match.queue_name} &middot; patch {sheet.match.patch}
        {sheet.lane_opponent && <> &middot; vs {sheet.lane_opponent.champion}</>}
      </p>

      <p style={{ fontSize: 18, fontWeight: 600, marginTop: 16 }}>
        {narrative.headline}
      </p>

      {narrative.what_went_well.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <SectionHeading>What went well</SectionHeading>
          <ul>
            {narrative.what_went_well.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {narrative.narrations.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <SectionHeading>Focus areas</SectionHeading>
          {narrative.narrations.map((n) => {
            const finding = sheet.findings.find((f) => f.id === n.finding_id);
            return (
              <div
                key={n.finding_id}
                style={{
                  border: "1px solid #eee",
                  borderRadius: 8,
                  padding: 12,
                  marginTop: 8,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                  }}
                >
                  <strong>{finding?.title ?? n.finding_id}</strong>
                  {finding && (
                    <span
                      style={{
                        fontSize: 12,
                        color: SEVERITY_COLOR[finding.severity] ?? "#555",
                        textTransform: "uppercase",
                      }}
                    >
                      {finding.severity}
                    </span>
                  )}
                </div>
                <p style={{ marginTop: 6 }}>{n.explanation}</p>
                <p style={{ marginTop: 6, color: "#444" }}>
                  <strong>Fix:</strong> {n.fix}
                </p>
                {n.drill && (
                  <p style={{ marginTop: 6, color: "#444" }}>
                    <strong>Drill:</strong> {n.drill}
                  </p>
                )}
                {finding && finding.evidence.length > 0 && (
                  <ul style={{ marginTop: 8, fontSize: 13, color: "#666" }}>
                    {finding.evidence.map((e, i) => (
                      <li key={i}>
                        {e.label}: {e.value}
                        {e.unit === "percent" ? "%" : ""}
                        {e.peer_value !== null ? ` (peer: ${e.peer_value})` : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}

      <p style={{ marginTop: 16 }}>{narrative.closing}</p>

      {sheet.metrics.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <SectionHeading>Metrics</SectionHeading>
          <table style={{ width: "100%", fontSize: 14, borderCollapse: "collapse" }}>
            <tbody>
              {sheet.metrics.map((m) => (
                <tr key={m.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                  <td style={{ padding: "6px 0" }}>{m.label}</td>
                  <td style={{ padding: "6px 0", textAlign: "right" }}>{m.value}</td>
                  <td style={{ padding: "6px 0", textAlign: "right", color: "#888" }}>
                    {m.comparisons[0]
                      ? `rank ${m.comparisons[0].rank_in_lobby ?? "?"}/10`
                      : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sheet.clean_checks.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <SectionHeading>Checked, no issues</SectionHeading>
          <ul style={{ fontSize: 14, color: "#444" }}>
            {sheet.clean_checks.map((c) => (
              <li key={c.id}>{c.title}</li>
            ))}
          </ul>
        </div>
      )}

      {result.used_fallback && (
        <p style={{ marginTop: 16, fontSize: 13, color: "#a16207" }}>
          Note: Claude&apos;s narration didn&apos;t pass validation, so this is a
          simplified fallback summary instead.
        </p>
      )}
    </section>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 style={{ fontSize: 14, textTransform: "uppercase", color: "#666" }}>
      {children}
    </h3>
  );
}
