import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CannotSeePanel } from "./CannotSeePanel";

const EIGHT_ITEMS = [
  "Ward placement locations",
  "Positioning between minute marks",
  "Teamfight spacing or mechanical execution",
  "Whether a death was intentional",
  "Communication or premade status",
  "Exact recall timings",
  "Champion matchup difficulty",
  "The player's rank relative to anyone outside this match",
];

describe("CannotSeePanel", () => {
  it("renders nothing when there are no items", () => {
    const { container } = render(<CannotSeePanel items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows only the first 4 of 8 items collapsed, with a correct count toggle", () => {
    render(<CannotSeePanel items={EIGHT_ITEMS} />);
    expect(screen.getByText(EIGHT_ITEMS[0])).toBeInTheDocument();
    expect(screen.getByText(EIGHT_ITEMS[3])).toBeInTheDocument();
    expect(screen.queryByText(EIGHT_ITEMS[4])).not.toBeInTheDocument();
    expect(screen.getByText("4 of 8 · show all")).toBeInTheDocument();
  });

  it("expands to show all items on click", async () => {
    const user = userEvent.setup();
    render(<CannotSeePanel items={EIGHT_ITEMS} />);
    await user.click(screen.getByText("4 of 8 · show all"));
    for (const item of EIGHT_ITEMS) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
  });

  it("shows no toggle when there are 4 or fewer items", () => {
    render(<CannotSeePanel items={EIGHT_ITEMS.slice(0, 3)} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
