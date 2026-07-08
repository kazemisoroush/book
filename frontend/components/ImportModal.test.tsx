import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/studio", () => ({
  startRun: vi.fn().mockResolvedValue({ run_id: "r1", workflow: "parse", state: "running" }),
}));

import { ImportModal } from "./ImportModal";
import { startRun } from "@/lib/studio";

const URL = "https://www.gutenberg.org/cache/epub/2197/pg2197-images.zip";

describe("ImportModal", () => {
  it("starts a parse run for the given Gutenberg URL and shows the started state", async () => {
    const onStarted = vi.fn();
    render(<ImportModal onClose={() => {}} onStarted={onStarted} />);

    fireEvent.change(screen.getByLabelText("Gutenberg URL"), { target: { value: URL } });
    fireEvent.click(screen.getByRole("button", { name: "Import book" }));

    await waitFor(() =>
      expect(startRun).toHaveBeenCalledWith({
        workflow: "parse",
        url: URL,
        startChapter: 1,
        refresh: false,
      }),
    );
    expect(await screen.findByText("Parsing started")).toBeInTheDocument();
    await waitFor(() => expect(onStarted).toHaveBeenCalled());
  });

  it("closes on the close button", () => {
    const onClose = vi.fn();
    render(<ImportModal onClose={onClose} onStarted={() => {}} />);
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalled();
  });
});
