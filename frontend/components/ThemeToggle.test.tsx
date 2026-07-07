import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ThemeToggle } from "./ThemeToggle";

afterEach(() => {
  delete document.documentElement.dataset.theme;
});

describe("ThemeToggle", () => {
  it("switches the document theme to light and back", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");

    fireEvent.click(button);
    expect(document.documentElement.dataset.theme).toBe("light");

    fireEvent.click(button);
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});
