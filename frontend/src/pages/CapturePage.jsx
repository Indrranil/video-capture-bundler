import React, { useEffect, useState } from "react";
import {
  getCameras,
  getCaptures,
  getLiveStatus,
  livePreviewUrl,
  startLiveRecording,
  stopLiveRecording,
  uploadCapture,
} from "../api.js";

function VerdictBadge({ verdict }) {
  if (verdict === 1) return <span className="badge badge-anomaly">anomaly</span>;
  if (verdict === 0) return <span className="badge badge-normal">normal</span>;
  return <span className="badge badge-muted">—</span>;
}

// Shows the gap since the previous chunk for that camera — "ok" (green) means bundling fired on
// schedule, "gap" (red) flags a likely missed cycle. Null means this is the first chunk seen for
// that camera, nothing to compare against yet.
function BundlingBadge({ gapSec, status }) {
  if (status == null || gapSec == null) return <span className="badge badge-muted">first</span>;
  const label = gapSec < 60 ? `${gapSec}s` : `${Math.floor(gapSec / 60)}m${gapSec % 60}s`;
  return <span className={`badge ${status === "ok" ? "badge-normal" : "badge-anomaly"}`}>{label}</span>;
}

function formatElapsed(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function CapturePage() {
  const [cameras, setCameras] = useState([]);
  const [camera, setCamera] = useState("");
  const [adhocUrl, setAdhocUrl] = useState("");
  const [captures, setCaptures] = useState([]);
  const [status, setStatus] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [previewNonce, setPreviewNonce] = useState(0); // bumping this remounts <img>, forcing a fresh stream
  const [liveStatus, setLiveStatus] = useState({ recording: false });
  const [busy, setBusy] = useState(false);
  const [uploadingId, setUploadingId] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);

  useEffect(() => {
    getCameras().then((list) => {
      setCameras(list);
      if (list.length) setCamera(list[0].name);
    });
  }, []);

  useEffect(() => {
    const refresh = () => getCaptures().then(setCaptures);
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const refresh = () => getLiveStatus().then(setLiveStatus).catch(() => {});
    refresh();
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, []);

  const selectedCamera = adhocUrl ? "__adhoc__" : camera;

  const togglePreview = () => {
    if (!showPreview) setPreviewNonce((n) => n + 1);
    setShowPreview((v) => !v);
  };

  const onStart = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const result = await startLiveRecording({
        camera: selectedCamera,
        adhoc_rtsp_url: adhocUrl || null,
      });
      setStatus({ type: "ok", text: `Recording started: ${result.camera}` });
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    } finally {
      setBusy(false);
    }
  };

  const onStop = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const result = await stopLiveRecording();
      setStatus({ type: "ok", text: result.message });
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    } finally {
      setBusy(false);
    }
  };

  const onUpload = async (chunkId) => {
    setUploadingId(chunkId);
    setUploadStatus(null);
    try {
      const result = await uploadCapture(chunkId);
      setUploadStatus({
        type: result.ok ? "ok" : "error",
        text: `${chunkId}: ${result.message}`,
      });
      getCaptures().then(setCaptures);
    } catch (err) {
      setUploadStatus({ type: "error", text: `${chunkId}: ${err.message}` });
    } finally {
      setUploadingId(null);
    }
  };

  return (
    <div>
      <div className="card">
        <h2>Camera</h2>
        <div className="field-row">
          <label className="field-label">Camera</label>
          <div className="field-control">
            <select value={camera} onChange={(e) => setCamera(e.target.value)} disabled={liveStatus.recording}>
              {cameras.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.ip}){c.rtsp_url ? "" : " — no RTSP"}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="field-row">
          <label className="field-label">Ad-hoc RTSP override</label>
          <div className="field-control">
            <input
              type="text"
              placeholder="rtsp://... (optional, overrides camera choice)"
              value={adhocUrl}
              onChange={(e) => setAdhocUrl(e.target.value)}
              disabled={liveStatus.recording}
            />
          </div>
        </div>

        <div className="field-row">
          <label className="field-label">Live preview</label>
          <div className="field-control">
            <button type="button" className="btn btn-primary" onClick={togglePreview}>
              {showPreview ? "Hide preview" : "Show preview"}
            </button>
          </div>
        </div>
        {showPreview && (
          <img
            key={previewNonce}
            className="live-preview"
            src={livePreviewUrl(selectedCamera, adhocUrl)}
            alt="camera preview"
          />
        )}

        <div className="field-row">
          <label className="field-label">Recording</label>
          <div className="field-control test-upload-controls">
            {liveStatus.recording ? (
              <>
                <span className="badge badge-anomaly">
                  ● REC {liveStatus.camera} — {formatElapsed(liveStatus.elapsed_sec)}
                </span>
                <button type="button" className="btn btn-danger" onClick={onStop} disabled={busy}>
                  Stop
                </button>
              </>
            ) : (
              <button type="button" className="btn btn-primary" onClick={onStart} disabled={busy}>
                Start recording
              </button>
            )}
          </div>
        </div>
        {status && <div className={`status-banner ${status.type}`}>{status.text}</div>}
      </div>

      <section className="card">
        <h2>Recent captures</h2>
        {captures.length === 0 ? (
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
                <th>Upload</th>
              </tr>
            </thead>
            <tbody>
              {captures.map((c) => (
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
    </div>
  );
}
