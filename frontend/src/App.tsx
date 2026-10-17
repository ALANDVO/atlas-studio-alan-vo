import { useEffect, useState } from "react";
import apiClient, { ApiError } from "./api/client";
import { Header } from "./components/Header";
import { LoadingState } from "./components/LoadingState";
import { PostingsPage } from "./pages/PostingsPage";
import { ScoringPage } from "./pages/ScoringPage";
import type { User } from "./types";

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<"postings" | "scoring">("postings");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .getCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const handleLogin = (role: string) => {
    apiClient
      .demoLogin(role)
      .then((resp) => {
        apiClient.setCsrfToken(resp.csrf_token);
        setUser(resp.user);
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          console.error(`Login failed: ${err.message}`);
        } else {
          console.error("Login failed");
        }
      });
  };

  const handleLogout = () => {
    apiClient
      .logout()
      .then(() => {
        apiClient.clearCsrfToken();
        setUser(null);
      })
      .catch(() => {
        apiClient.clearCsrfToken();
        setUser(null);
      });
  };

  if (loading) {
    return <LoadingState message="Starting Atlas Studio..." />;
  }

  return (
    <div className="app">
      <Header
        user={user}
        onLogin={handleLogin}
        onLogout={handleLogout}
        view={view}
        onViewChange={setView}
      />
      <main className="main">
        {view === "postings" ? (
          <PostingsPage user={user} />
        ) : (
          <ScoringPage user={user} />
        )}
      </main>
    </div>
  );
}

export default App;