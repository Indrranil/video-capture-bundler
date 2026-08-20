import React, { useEffect, useState } from "react";
import { addCamera, deleteCamera, getCameras, updateCamera } from "../api.js";

export default function CamerasPage() {
  const [cameras, setCameras] = useState([]);
  const [edits, setEdits] = useState({});
  const [newCam, setNewCam] = useState({ name: "", ip: "", rtsp_url: "" });
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(null); // camera name currently saving/deleting, or "add"

  const load = () => {
    getCameras().then((list) => {
      setCameras(list);
      const e = {};
      for (const c of list) e[c.name] = { ip: c.ip, rtsp_url: c.rtsp_url };
      setEdits(e);
    });
  };

  useEffect(load, []);

  const setEditField = (name, field, value) =>
    setEdits((prev) => ({ ...prev, [name]: { ...prev[name], [field]: value } }));

  const onAdd = async (e) => {
    e.preventDefault();
    setBusy("add");
    setStatus(null);
    try {
      const result = await addCamera(newCam);
      setStatus({ type: "ok", text: `Added ${newCam.name}. ${result.restart}` });
      setNewCam({ name: "", ip: "", rtsp_url: "" });
      load();
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    } finally {
      setBusy(null);
    }
  };

  const onSave = async (name) => {
    setBusy(name);
    setStatus(null);
    try {
      const result = await updateCamera(name, edits[name]);
      setStatus({ type: "ok", text: `Updated ${name}. ${result.restart}` });
      load();
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    } finally {
      setBusy(null);
    }
  };

  const onDelete = async (name) => {
    if (!window.confirm(`Delete camera "${name}"? This restarts the recorder container.`)) return;
    setBusy(name);
    setStatus(null);
    try {
      const result = await deleteCamera(name);
      setStatus({ type: "ok", text: `Deleted ${name}. ${result.restart}` });
      load();
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <form className="card" onSubmit={onAdd}>
        <h2>Add a camera</h2>
        <div className="field-row">
          <label className="field-label">Name</label>
          <div className="field-control">
            <input
              type="text"
              value={newCam.name}
              onChange={(e) => setNewCam({ ...newCam, name: e.target.value })}
              placeholder="cam12"
              required
            />
          </div>
        </div>
        <div className="field-row">
          <label className="field-label">IP</label>
          <div className="field-control">
            <input
              type="text"
              value={newCam.ip}
              onChange={(e) => setNewCam({ ...newCam, ip: e.target.value })}
              placeholder="192.168.1.50"
              required
            />
          </div>
        </div>
        <div className="field-row">
          <label className="field-label">RTSP URL</label>
          <div className="field-control">
            <input
              type="text"
              value={newCam.rtsp_url}
              onChange={(e) => setNewCam({ ...newCam, rtsp_url: e.target.value })}
              placeholder="rtsp://... (optional)"
            />
          </div>
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy === "add"}>
          {busy === "add" ? "Adding..." : "Add camera"}
        </button>
      </form>

      <section className="card">
        <h2>Cameras ({cameras.length})</h2>
        {cameras.length === 0 ? (
          <p className="empty-state">No cameras configured yet — add one above.</p>
        ) : (
          cameras.map((c) => (
            <div className="field-row camera-row" key={c.name}>
              <label className="field-label">{c.name}</label>
              <div className="field-control camera-row-controls">
                <input
                  type="text"
                  value={edits[c.name]?.ip ?? ""}
                  onChange={(e) => setEditField(c.name, "ip", e.target.value)}
                  placeholder="IP"
                />
                <input
                  type="text"
                  value={edits[c.name]?.rtsp_url ?? ""}
                  onChange={(e) => setEditField(c.name, "rtsp_url", e.target.value)}
                  placeholder="rtsp://..."
                />
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={busy === c.name}
                  onClick={() => onSave(c.name)}
                >
                  Save
                </button>
                <button
                  className="btn btn-danger"
                  type="button"
                  disabled={busy === c.name}
                  onClick={() => onDelete(c.name)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </section>
      {status && <div className={`status-banner ${status.type}`}>{status.text}</div>}
    </div>
  );
}
