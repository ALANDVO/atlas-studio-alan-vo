import { useState } from "react";
import type { User } from "../types";

interface HeaderProps {
  user: User | null;
  onLogin: (role: string) => void;
  onLogout: () => void;
  view: "postings" | "scoring";
  onViewChange: (view: "postings" | "scoring") => void;
}

export function Header({ user, onLogin, onLogout, view, onViewChange }: HeaderProps) {
  return (
    <header className="header">
      <h1>Atlas <span className="accent">Studio</span></h1>
      <nav className="nav">
        <button
          onClick={() => onViewChange("postings")}
          className={view === "postings" ? "active" : ""}
        >
          Postings
        </button>
        <button
          onClick={() => onViewChange("scoring")}
          className={view === "scoring" ? "active" : ""}
        >
          Scoring &amp; Evaluation
        </button>
      </nav>
      <div className="auth-section">
        {user ? (
          <>
            <span className="user-badge">{user.name} ({user.role})</span>
            <button className="btn btn-secondary" onClick={onLogout}>Logout</button>
          </>
        ) : (
          <LoginForm onLogin={onLogin} />
        )}
      </div>
    </header>
  );
}

function LoginForm({ onLogin }: { onLogin: (role: string) => void }) {
  const [role, setRole] = useState("viewer");
  return (
    <>
      <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Role">
        <option value="viewer">Viewer</option>
        <option value="analyst">Analyst</option>
        <option value="admin">Admin</option>
      </select>
      <button className="btn" onClick={() => onLogin(role)}>Login (Demo)</button>
    </>
  );
}