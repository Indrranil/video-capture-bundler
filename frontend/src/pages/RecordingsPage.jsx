import React from "react";
import CapturesTable from "../components/CapturesTable.jsx";

// Everything main.py's own loop has recorded automatically — as opposed to the Manual Capture
// page's on-demand start/stop recordings. Same shared table, filtered to source="auto".
export default function RecordingsPage() {
  return (
    <div>
      <CapturesTable source="auto" heading="Automatic recordings" pollMs={5000} />
    </div>
  );
}
