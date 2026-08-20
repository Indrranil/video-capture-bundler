import React, { useEffect, useState } from "react";
import { captureVideoUrl, getCaptures, uploadCapture } from "../api.js";

function VerdictBadge({ verdict }) {
  if (verdict === 1) return <span className="badge badge-anomaly">anomaly</span>;
  if (verdict === 0) return <span className="badge badge-normal">normal</span>;
  return <span className="badge badge-muted">—</span>;
}

// Shows the gap since the previous AUTO chunk for that camera — "ok" (green) means bundling
// fired on schedule, "gap" (red) flags a likely missed cycle. Muted "first"/"—" covers manual
// chunks (no schedule to compare against) and the very first auto chunk seen for a camera.
function BundlingBadge({ gapSec, status }) {
  if (status == null || gapSec == null) return <span className="badge badge-muted">—</span>;
  const label = gapSec < 60 ? `${gapSec}s` : `${Math.floor(gapSec / 60)}m${gapSec % 60}s`;
  return <span className={`badge ${status === "ok" ? "badge-normal" : "badge-anomaly"}`}>{label}</span>;
}

// Shared by the Manual Capture page (source="manual") and the Recordings page (source="auto") —
// same table, same upload/view actions, just filtered to a different slice of chunks.json.
export default function CapturesTable({ source, heading, pollMs = 3000, onTotal }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [uploadingId, setUploadingId] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);

  const refresh = () =>
    getCaptures(source).then((data) => {
      setRows(data.rows);
      setTotal(data.total);
      if (onTotal) onTotal(data.total);
    });

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  const onUpload = async (chunkId) => {
    setUploadingId(chunkId);
    setUploadStatus(null);
    try {
      const result = await uploadCapture(chunkId);
      setUploadStatus({ type: result.ok ? "ok" : "error", text: `${chunkId}: ${result.message}` });
      refresh();
    } catch (err) {
      setUploadStatus({ type: "error", text: `${chunkId}: ${err.message}` });
    } finally {
      setUploadingId(null);
    }
  };

  return (
    <section className="card">
      <h2>
        {heading}
        {total ? ` (${total})` : ""}
      </h2>
      {rows.length === 0 ? (
        <p className="empty-state">No captures yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Chunk</th>
              <th>Camera</th>
              <th>Started</th>
              <th>Bundling gap</th>
              <th>Verdict</th>
              <th>Zip</th>
              <th>View</th>
              <th>Upload</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.chunk_id}>
                <td>{c.chunk_id}</td>
                <td>{c.camera_name}</td>
                <td>{c.started_at_ist}</td>
                <td>
                  <BundlingBadge gapSec={c.gap_sec} status={c.bundling_status} />
                </td>
                <td>
                  <VerdictBadge verdict={c.verdict} />
                </td>
                <td>
                  {c.zip_path ? (
                    <span className="badge badge-normal">yes</span>
                  ) : (
                    <span className="badge badge-muted">—</span>
                  )}
                </td>
                <td>
                  {c.has_video ? (
                    <a
                      className="badge badge-normal"
                      href={captureVideoUrl(c.chunk_id)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      view
                    </a>
                  ) : (
                    <span className="badge badge-muted">—</span>
                  )}
                </td>
                <td>
                  {c.uploaded_url ? (
                    <a
                      className="badge badge-normal"
                      href={c.uploaded_url}
                      target="_blank"
                      rel="noreferrer"
                      title={c.uploaded_url}
                    >
                      uploaded
                    </a>
                  ) : c.zip_path ? (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => onUpload(c.chunk_id)}
                      disabled={uploadingId === c.chunk_id}
                    >
                      {uploadingId === c.chunk_id ? "Uploading..." : "Upload"}
                    </button>
                  ) : (
                    <span className="badge badge-muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {uploadStatus && <div className={`status-banner ${uploadStatus.type}`}>{uploadStatus.text}</div>}
    </section>
  );
}
