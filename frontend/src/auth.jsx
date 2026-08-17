import { createContext, useContext, useState } from "react";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(
    localStorage.getItem("token")
  );

  function setToken(token) {
    localStorage.setItem("token", token);
    setTokenState(token);
  }

  function logout() {
    localStorage.removeItem("token");
    setTokenState(null);
  }

  return (
    <AuthContext.Provider value={{ token, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
