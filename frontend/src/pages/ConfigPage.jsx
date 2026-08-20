import React, { useEffect, useMemo, useState } from "react";
import { getConfig, updateConfig } from "../api.js";
import TestStorageUpload from "../components/TestStorageUpload.jsx";

export default function ConfigPage() {
  const [sections, setSections] = useState([]);
  const [providerFieldGroups, setProviderFieldGroups] = useState({});
  const [values, setValues] = useState({});
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    getConfig().then((data) => {
      setSections(data.sections);
      setProviderFieldGroups(data.provider_field_groups || {});
      const initial = {};
      for (const section of data.sections) {
        for (const field of section.fields) {
          initial[field.key] =
            field.type === "bool" ? String(field.value).toLowerCase() === "true" : field.value;
        }
      }
      setValues(initial);
    });
  };

  useEffect(load, []);

  // Every field name that belongs to SOME provider's group (i.e. is provider-specific) —
  // used below to hide whichever provider isn't currently selected.
  const providerSpecificFields = useMemo(() => {
    const all = new Set();
    for (const fields of Object.values(providerFieldGroups)) fields.forEach((f) => all.add(f));
    return all;
  }, [providerFieldGroups]);

  const activeProviderFields = useMemo(
    () => new Set(providerFieldGroups[values.STORAGE_PROVIDER] || []),
    [providerFieldGroups, values.STORAGE_PROVIDER]
  );

  const isFieldVisible = (key) => !providerSpecificFields.has(key) || activeProviderFields.has(key);

  const setField = (key, value) => setValues((v) => ({ ...v, [key]: value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setStatus(null);
    try {
      const payload = {};
      for (const [k, v] of Object.entries(values)) {
        payload[k] = typeof v === "boolean" ? (v ? "true" : "false") : String(v);
      }
      const result = await updateConfig(payload);
      setStatus({
        type: "ok",
        text: result.changed.length
          ? `Saved. Changed: ${result.changed.join(", ")}. ${result.restart}`
          : "No changes to save.",
      });
      load();
    } catch (err) {
      setStatus({ type: "error", text: `Error: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={onSubmit}>
      {sections.map((section) => (
        <section className="card" key={section.name}>
          <h2>{section.name}</h2>
          {section.fields
            .filter((field) => isFieldVisible(field.key))
            .map((field) => (
              <div className="field-row" key={field.key}>
                <label className="field-label">{field.label}</label>
                <div className="field-control">
                  {field.options ? (
                    <select
                      value={values[field.key] ?? ""}
                      onChange={(e) => setField(field.key, e.target.value)}
                    >
                      {field.options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : field.type === "bool" ? (
                    <label className="toggle">
                      <input
                        type="checkbox"
                        checked={!!values[field.key]}
                        onChange={(e) => setField(field.key, e.target.checked)}
                      />
                      <span className="slider" />
                    </label>
                  ) : field.secret ? (
                    <input
                      type="password"
                      placeholder="(unchanged — leave blank to keep)"
                      value={values[field.key] || ""}
                      onChange={(e) => setField(field.key, e.target.value)}
                    />
                  ) : (
                    <input
                      type="text"
                      value={values[field.key] ?? ""}
                      onChange={(e) => setField(field.key, e.target.value)}
                    />
                  )}
                </div>
              </div>
            ))}
          {section.name === "Storage / Upload" && <TestStorageUpload values={values} />}
        </section>
      ))}
      <button className="btn btn-primary" type="submit" disabled={saving}>
        {saving ? "Saving..." : "Save & restart recorder"}
      </button>
      {status && <div className={`status-banner ${status.type}`}>{status.text}</div>}
    </form>
  );
}
