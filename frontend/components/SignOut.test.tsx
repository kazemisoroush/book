import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({
  isAuthenticated: vi.fn(),
  signOut: vi.fn(),
}));

import { isAuthenticated } from "@/lib/auth";

import { SignOut } from "./SignOut";

describe("SignOut", () => {
  it("shows the control when signed in", () => {
    vi.mocked(isAuthenticated).mockReturnValue(true);
    render(<SignOut />);
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("hides when not signed in", () => {
    vi.mocked(isAuthenticated).mockReturnValue(false);
    render(<SignOut />);
    expect(screen.queryByRole("button", { name: /sign out/i })).not.toBeInTheDocument();
  });
});
