import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getToken } from "../api/client";
import { login as loginRequest, logout as logoutRequest } from "../api/auth";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  signIn: (identification: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getToken().then((token) => {
      setIsAuthenticated(Boolean(token));
      setIsLoading(false);
    });
  }, []);

  async function signIn(identification: string, password: string) {
    await loginRequest(identification, password);
    setIsAuthenticated(true);
  }

  async function signOut() {
    await logoutRequest();
    setIsAuthenticated(false);
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
