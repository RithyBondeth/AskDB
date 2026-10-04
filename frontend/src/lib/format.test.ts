import { describe, expect, it } from "vitest";
import { formatAxis, formatCell, formatHero, isNumericColumn, toCsv } from "@/lib/format";

describe("formatCell", () => {
  it("shows NULL, integers as-is, and floats to 2 places", () => {
    expect(formatCell(null)).toBe("NULL");
    expect(formatCell(1234567)).toBe("1234567"); // no grouping: ids and years stay readable
    expect(formatCell(2.71828)).toMatch(/^2[.,]72$/);
    expect(formatCell("Rock")).toBe("Rock");
  });
});

describe("formatHero and formatAxis", () => {
  it("compact large numbers only", () => {
    expect(formatHero(12_900)).toMatch(/^12[.,]9K$/);
    expect(formatHero(42)).toBe("42");
    expect(formatHero("n/a")).toBe("n/a");
    expect(formatAxis(1500)).toMatch(/^1[.,]5K$/);
    expect(formatAxis(250)).toBe("250");
  });
});

describe("toCsv", () => {
  it("quotes commas, quotes and newlines, and leaves NULL empty", () => {
    const csv = toCsv(
      ["name", "note"],
      [
        ["AC/DC", 'say "hi"'],
        ["Smith, J", null],
        ["two\nlines", 3],
      ],
    );
    expect(csv).toBe('name,note\nAC/DC,"say ""hi"""\n"Smith, J",\n"two\nlines",3');
  });
});

describe("isNumericColumn", () => {
  it("allows NULLs but not text, and needs at least one row", () => {
    expect(isNumericColumn([[1], [null], [2.5]], 0)).toBe(true);
    expect(isNumericColumn([[1], ["2"]], 0)).toBe(false);
    expect(isNumericColumn([], 0)).toBe(false);
  });
});
