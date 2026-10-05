// A stand-in for an OpenAI-compatible chat API, so the browser tests run the real
// app (Next.js -> FastAPI -> validate -> SQLite) without a model key or network.
// SQL generation gets canned Chinook SQL picked by a keyword in the question;
// result summaries get a fixed sentence.
import { createServer } from "node:http";

const PORT = Number(process.env.MOCK_MODEL_PORT ?? 8765);

const ANSWERS = [
  {
    match: "albums",
    sql:
      "SELECT ar.Name, COUNT(*) AS album_count FROM Album al JOIN Artist ar " +
      "ON ar.ArtistId = al.ArtistId GROUP BY ar.Name ORDER BY album_count DESC LIMIT 10",
  },
  // First try is wrong on purpose (no such column), so self-correction runs.
  {
    match: "genre",
    sql: "SELECT GenreName FROM Genre",
    repaired: "SELECT Name FROM Genre ORDER BY Name",
  },
  {
    match: "sales",
    sql: "SELECT region, SUM(amount) AS total FROM sales GROUP BY region ORDER BY total DESC",
  },
];

function reply(messages) {
  const system = messages[0]?.content ?? "";
  if (system.includes("explain query results")) return "Iron Maiden has the most albums, with 21.";
  const question = (
    messages.findLast((m) => m.role === "user" && m.content.startsWith("Q:"))?.content ?? ""
  ).toLowerCase();
  const answer = ANSWERS.find((a) => question.includes(a.match)) ?? ANSWERS[0];
  const repairing = messages.at(-1)?.content.startsWith("That query failed");
  const sql = repairing && answer.repaired ? answer.repaired : answer.sql;
  return "```sql\n" + sql + "\n```\nAnswers the question.";
}

createServer((req, res) => {
  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", () => {
    if (req.method === "GET") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ data: [{ id: "mock-model" }] }));
    }
    const { messages } = JSON.parse(body || "{}");
    res.writeHead(200, { "content-type": "application/json" });
    res.end(
      JSON.stringify({
        choices: [{ message: { content: reply(messages ?? []) }, finish_reason: "stop" }],
      }),
    );
  });
}).listen(PORT, "127.0.0.1", () => console.log(`mock model on :${PORT}`));
