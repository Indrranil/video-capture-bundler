import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import ConfigPage from "./pages/ConfigPage.jsx";
import CamerasPage from "./pages/CamerasPage.jsx";
import CapturePage from "./pages/CapturePage.jsx";
import RecordingsPage from "./pages/RecordingsPage.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="app-header">
          <h1>video-capture-bundler</h1>
          <p className="subtitle">Factory camera pipeline — config &amp; manual capture</p>
        </header>
        <nav className="tabs">
          <NavLink to="/config" className={({ isActive }) => "tab" + (isActive ? " active" : "")}>
            Config
          </NavLink>
          <NavLink to="/cameras" className={({ isActive }) => "tab" + (isActive ? " active" : "")}>
            Cameras
          </NavLink>
          <NavLink to="/capture" className={({ isActive }) => "tab" + (isActive ? " active" : "")}>
            Manual Capture
          </NavLink>
          <NavLink to="/recordings" className={({ isActive }) => "tab" + (isActive ? " active" : "")}>
            Recordings
          </NavLink>
        </nav>
        <Routes>
          <Route path="/" element={<ConfigPage />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/cameras" element={<CamerasPage />} />
          <Route path="/capture" element={<CapturePage />} />
          <Route path="/recordings" element={<RecordingsPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
