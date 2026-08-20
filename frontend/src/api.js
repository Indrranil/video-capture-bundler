async function request(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body && body.detail ? body.detail : res.statusText;
    throw new Error(detail);
  }
  return body;
}

export const getConfig = () => request("/api/config");

export const updateConfig = (values) =>
  request("/api/config", { method: "POST", body: JSON.stringify({ values }) });

// Not routed through request() — this is multipart, not JSON, so it needs its own fetch
// (setting Content-Type manually would break the browser's auto-generated form boundary).
export const testStorageUpload = async (file, values) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("values", JSON.stringify(values));
  const res = await fetch("/api/config/test-storage", { method: "POST", body: formData });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error((body && body.detail) || res.statusText);
  }
  return body;
};

export const getCameras = () => request("/api/cameras");

export const addCamera = (payload) =>
  request("/api/cameras", { method: "POST", body: JSON.stringify(payload) });

export const updateCamera = (name, payload) =>
  request(`/api/cameras/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify(payload) });

export const deleteCamera = (name) =>
  request(`/api/cameras/${encodeURIComponent(name)}`, { method: "DELETE" });

export const getCaptures = (source, limit) => {
  const params = new URLSearchParams();
  if (source) params.set("source", source);
  if (limit) params.set("limit", limit);
  const qs = params.toString();
  return request(`/api/captures${qs ? `?${qs}` : ""}`);
};

export const uploadCapture = (chunkId) =>
  request(`/api/captures/${encodeURIComponent(chunkId)}/upload`, { method: "POST" });

// Opens in a new tab: the browser plays it if it can decode the codec/container, otherwise
// falls back to its normal "can't display this, download it" behavior (see the AVI/browser
// codec-support caveat called out alongside this feature).
export const captureVideoUrl = (chunkId) => `/api/captures/${encodeURIComponent(chunkId)}/video`;

// The <img> tag hits this URL directly (it's a multipart/x-mixed-replace stream, not JSON) —
// this just builds the query string consistently with the rest of the API layer.
export const livePreviewUrl = (camera, adhocRtspUrl) => {
  const params = new URLSearchParams({ camera: camera || "__adhoc__" });
  if (adhocRtspUrl) params.set("adhoc_rtsp_url", adhocRtspUrl);
  return `/api/live/preview?${params.toString()}`;
};

export const getLiveStatus = () => request("/api/live/status");

export const startLiveRecording = (payload) =>
  request("/api/live/start", { method: "POST", body: JSON.stringify(payload) });

export const stopLiveRecording = () => request("/api/live/stop", { method: "POST" });
