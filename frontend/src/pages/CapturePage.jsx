import React, { useEffect, useState } from "react";
import { getCameras, getCaptures, triggerCapture } from "../api.js";

function VerdictBadge({ verdict }) {
  if (verdict === 1) return <span className="badge badge-anomaly">anomaly</span>;
  if (verdict === 0) return <span className="badge badge-normal">normal</span>;
  return <span className="badge badge-muted">—</span>;
}

export default function CapturePage() {
  const [cameras, setCameras] = useState([]);
  const [camera, setCamera] = useState("");
  const [adhocUrl, setAdhocUrl] = useState("");
  const [duration, setDuration] = useState("");
  const [captures, setCaptures] = useState([]);
  const [status, setStatus] = useState(null);

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

  const onSubmit = async (e) => {
    e.preventDefault();
    setStatus(null);
    try {
      const result = await triggerCapture({
        camera: adhocUrl ? "__adhoc__" : camera,
        adhoc_rtsp_url: adhocUrl || null,
        duration_override: duration ? parseInt(duration, 10) : null,
      });
      setStatus({ type: "ok", text: `Capture started: ${result.camera} (${result.duration}s)` });
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    }
  };

  return (
    <div>
      <form className="card" onSubmit={onSubmit}>
        <h2>Trigger a manual capture</h2>
        <div className="field-row">
          <label className="field-label">Camera</label>
          <div className="field-control">
            <select value={camera} onChange={(e) => setCamera(e.target.value)}>
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
            />
          </div>
        </div>
        <div className="field-row">
          <label className="field-label">Duration override (s)</label>
          <div className="field-control">
            <input
              type="number"
              placeholder="default from config"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </div>
        </div>
        <button className="btn btn-primary" type="submit">
          Start manual capture
        </button>
        {status && <div className={`status-banner ${status.type}`}>{status.text}</div>}
      </form>

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
                <th>Verdict</th>
                <th>Zip</th>
              </tr>
            </thead>
            <tbody>
              {captures.map((c) => (
                <tr key={c.chunk_id}>
                  <td>{c.chunk_id}</td>
                  <td>{c.camera_name}</td>
                  <td>{c.started_at_ist}</td>
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
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
