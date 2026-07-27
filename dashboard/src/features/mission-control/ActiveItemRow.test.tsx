import { describe, expect, it } from "vitest";
import { ActiveItemRow } from "./ActiveItemRow";

describe("ActiveItemRow", () => {
  it("is memoized to avoid unrelated mission updates rerendering stable rows", () => {
    const component = ActiveItemRow as unknown as { $$typeof?: symbol };

    expect(component.$$typeof).toBe(Symbol.for("react.memo"));
  });
});
