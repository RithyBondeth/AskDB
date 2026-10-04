import { isValidElement, type ReactElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { highlightSql } from "@/lib/sqlHighlight";

type Span = ReactElement<{ children: string; style: { color: string } }>;

const text = (nodes: ReactNode[]) =>
  nodes.map((n) => (isValidElement(n) ? (n as Span).props.children : String(n))).join("");

const colorOf = (nodes: ReactNode[], token: string) => {
  const span = nodes.find((n) => isValidElement(n) && (n as Span).props.children === token);
  return span ? (span as Span).props.style.color : null;
};

describe("highlightSql", () => {
  const sql = "SELECT COUNT(*), 'it''s' -- note\nFROM \"Track\" WHERE x > 1.5";
  const nodes = highlightSql(sql);

  it("keeps the text exactly", () => {
    expect(text(nodes)).toBe(sql);
  });

  it("colours each kind of token", () => {
    expect(colorOf(nodes, "SELECT")).toBe("var(--syn-keyword)");
    expect(colorOf(nodes, "COUNT")).toBe("var(--syn-func)");
    expect(colorOf(nodes, "'it''s'")).toBe("var(--syn-string)");
    expect(colorOf(nodes, "-- note")).toBe("var(--syn-comment)");
    expect(colorOf(nodes, "1.5")).toBe("var(--syn-number)");
    expect(colorOf(nodes, "x")).toBeNull(); // plain identifiers stay plain
  });
});
