import React, { useEffect, useState } from "react";
import { getCameras, getLiveStatus, livePreviewUrl, startLiveRecording, stopLiveRecording } from "../api.js";
import CapturesTable from "../components/CapturesTable.jsx";

function formatElapsed(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function CapturePage() {
  const [cameras, setCameras] = useState([]);
  const [camera, setCamera] = useState("");
  const [adhocUrl, setAdhocUrl] = useState("");
  const [status, setStatus] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [previewNonce, setPreviewNonce] = useState(0); // bumping this remounts <img>, forcing a fresh stream
  const [liveStatus, setLiveStatus] = useState({ recording: false });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getCameras().then((list) => {
      setCameras(list);
      if (list.length) setCamera(list[0].name);
    });
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

      <CapturesTable source="manual" heading="Recent manual captures" />
    </div>
  );
}
