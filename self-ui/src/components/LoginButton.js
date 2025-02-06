import React from "react";
import { useAuth } from "./../auth/AuthContext";

const LoginButton = () => {
  const { user, signInWithGoogle, logout } = useAuth();

  return (
    <div>
      {user ? (
        <div>
          <p>Welcome, {user.displayName}!</p>
          <button onClick={logout}>Log Out</button>
        </div>
      ) : (
        <button onClick={signInWithGoogle}>Log In with Google</button>
      )}
    </div>
  );
};

export default LoginButton;
