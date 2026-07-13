import { Suspense } from "react";

import { Review } from "./Review";

export default function ChapterReviewPage() {
  return (
    <Suspense fallback={<p className="muted-note">Opening the chapter…</p>}>
      <Review />
    </Suspense>
  );
}
