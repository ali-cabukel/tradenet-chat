import { useAuth } from "@/auth/AuthContext";
import { Spinner } from "@/components/ui";
import Chat from "@/pages/Chat";
import Login from "@/pages/Login";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Restoring your session…" />
      </div>
    );
  }

  if (!user) return <Login />;
  return <Chat />;
}
