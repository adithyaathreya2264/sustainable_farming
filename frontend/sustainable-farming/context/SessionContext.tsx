import React, { createContext, useContext, useMemo } from "react";
import { useAppState } from "../hooks/useAppState";
import { logout as logoutStore } from "../store/appStore";
import type { User } from "../types/models";

interface SessionContextValue {
  hydrated: boolean;
  isAuthenticated: boolean;
  user: User;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const hydrated = useAppState((s) => s.hydrated);
  const isAuthenticated = useAppState((s) => s.isAuthenticated);
  const user = useAppState((s) => s.user);

  const value = useMemo(
    () => ({ hydrated, isAuthenticated, user, logout: logoutStore }),
    [hydrated, isAuthenticated, user]
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
