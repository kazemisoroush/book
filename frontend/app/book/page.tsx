import { Suspense } from "react";

import { Workspace } from "./Workspace";

export default function BookPage() {
  return (
    <Suspense fallback={<p className="muted-note">Opening the dossier…</p>}>
      <Workspace />
    </Suspense>
  );
}
