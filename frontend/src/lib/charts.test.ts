import { describe, expect, it } from "vitest";
import { chartChoices, pivot, toRecords } from "@/lib/charts";
import type { ChartSpec } from "@/lib/types";

const spec = (type: ChartSpec["type"]): ChartSpec => ({ type, x: "x", y: ["y"], reason: "" });

describe("chartChoices", () => {
  it("offers the switches that make sense for each chart", () => {
    expect(chartChoices(spec("bar"))).toEqual(["bar", "line"]);
    expect(chartChoices(spec("line"))).toEqual(["bar", "line"]);
    expect(chartChoices(spec("pie"))).toEqual(["pie", "bar"]);
    expect(chartChoices(spec("scatter"))).toEqual(["scatter"]);
    expect(chartChoices(spec("none"))).toEqual([]);
  });
});

describe("pivot", () => {
  const columns = ["country", "genre", "revenue"];
  const rows = [
    ["US", "Rock", 10],
    ["US", "Jazz", 4],
    ["UK", "Rock", 7],
  ];

  it("turns long rows into one record per x, one key per group", () => {
    const { data, series } = pivot(columns, rows, "country", "genre", "revenue");
    expect(series).toEqual(["Rock", "Jazz"]);
    expect(data).toEqual([
      { country: "US", Rock: 10, Jazz: 4 },
      { country: "UK", Rock: 7 },
    ]);
  });

  it("folds groups past the palette into Other", () => {
    const many = ["a", "b", "c", "d"].map((g, i) => ["US", g, i + 1]);
    const { data, series } = pivot(columns, many, "country", "genre", "revenue", 3);
    expect(series).toEqual(["a", "b", "Other"]);
    expect(data).toEqual([{ country: "US", a: 1, b: 2, Other: 7 }]);
  });
});

describe("toRecords", () => {
  it("keys each row by column", () => {
    expect(toRecords(["a", "b"], [[1, "x"]])).toEqual([{ a: 1, b: "x" }]);
  });
});
