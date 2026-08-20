import React, { useState } from "react";
import { testStorageUpload } from "../api.js";

// Lets you verify Storage/Upload credentials BEFORE saving — uploads a real file using
// whatever's currently typed in the form above (even if unsaved), via the same upload_zip()
// code path finalize_day.py uses in production, so a pass here means the real thing will work.
export default function TestStorageUpload({ values }) {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState(null);
  const [testing, setTesting] = useState(false);

  const onTest = async () => {
    if (!file) {
      setStatus({ type: "error", text: "Pick a file first." });
      return;
    }
    setTesting(true);
    setStatus(null);
    try {
      const result = await testStorageUpload(file, values);
      setStatus({ type: result.ok ? "ok" : "error", text: result.message });
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="field-row test-upload-row">
      <label className="field-label">Test upload</label>
      <div className="field-control test-upload-controls">
        <input type="file" onChange={(e) => setFile(e.target.files[0] || null)} />
        <button type="button" className="btn btn-primary" onClick={onTest} disabled={testing}>
          {testing ? "Testing..." : "Test upload"}
        </button>
        <p className="test-upload-hint">
          Uploads this file for real with the settings above, even if not saved yet, to confirm
          the credentials work. The file is not deleted afterward — it lands under
          factory_location=connection-test so it's easy to find and remove from your bucket.
        </p>
        {status && <div className={`status-banner ${status.type}`}>{status.text}</div>}
      </div>
    </div>
  );
}
