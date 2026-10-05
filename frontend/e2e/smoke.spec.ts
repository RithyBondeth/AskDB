import { expect, type Locator, type Page, test } from "@playwright/test";

/** Ask a question in the composer; resolves with that answer's card once it's done. */
async function ask(page: Page, question: string): Promise<Locator> {
  const before = await page.locator("article").count();
  const box = page.getByLabel("Question", { exact: true });
  await box.fill(question);
  await box.press("Enter");
  const answer = page.locator("article").nth(before);
  await expect(answer.getByTitle("Ask again")).toBeVisible({ timeout: 30_000 });
  return answer;
}

test("asks a question and shows the answer, chart, table and SQL", async ({ page }) => {
  await page.goto("/");
  const answer = await ask(page, "Which artist has the most albums?");
  await expect(answer.getByText("Iron Maiden has the most albums, with 21.")).toBeVisible();
  await expect(answer.locator(".recharts-bar-rectangle").first()).toBeVisible();

  await answer.getByRole("button", { name: "Table", exact: true }).click();
  await expect(answer.getByRole("cell", { name: "Iron Maiden" })).toBeVisible();
  await expect(answer.getByRole("row")).toHaveCount(11); // header + 10 rows

  await answer.getByRole("button", { name: "SQL", exact: true }).click();
  await expect(answer.getByText("GROUP BY ar.Name")).toBeVisible();
});

test("fixes its own failing query", async ({ page }) => {
  await page.goto("/");
  const answer = await ask(page, "List every genre");
  await expect(answer.getByText("Self-corrected after 1 failed attempt")).toBeVisible();
  await answer.getByRole("button", { name: "Table", exact: true }).click();
  await expect(answer.getByRole("cell", { name: "Blues" })).toBeVisible();
});

test("edited SQL still can't change data", async ({ page }) => {
  await page.goto("/");
  const answer = await ask(page, "Which artist has the most albums?");
  await answer.getByRole("button", { name: "SQL", exact: true }).click();
  await answer.getByRole("button", { name: "Edit" }).click();
  await answer.getByLabel("SQL", { exact: true }).fill("DROP TABLE Artist");
  await answer.getByRole("button", { name: /^Run/ }).click();
  await expect(answer.getByText(/Blocked/)).toBeVisible();
});

test("uploads a CSV and answers from it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Use your own data" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "sales.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("region,amount\nNorth,10\nSouth,25\nNorth,5\n"),
  });
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(page.getByRole("button", { name: /^sales/ })).toBeVisible({ timeout: 15_000 });

  const answer = await ask(page, "Total sales by region");
  await answer.getByRole("button", { name: "Table", exact: true }).click();
  await expect(answer.getByRole("cell", { name: "South" })).toBeVisible();
  await expect(answer.getByRole("cell", { name: "25" })).toBeVisible();
});

test("a shared answer opens in another browser without asking again", async ({
  page,
  browser,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  const answer = await ask(page, "Which artist has the most albums?");
  await answer.getByRole("button", { name: "Share" }).click();
  await expect(answer.getByText("Link copied")).toBeVisible();
  const link = await page.evaluate(() => navigator.clipboard.readText());
  expect(link).toMatch(/\/\?a=[0-9a-f]{32}$/);

  // A fresh context is a different browser id: it can open the link only because it's shared.
  const other = await browser.newContext();
  const visitor = await other.newPage();
  await visitor.goto(link);
  await expect(visitor.getByText("Iron Maiden has the most albums, with 21.")).toBeVisible();
  await expect(visitor.locator("article")).toHaveCount(1);
  await other.close();
});
