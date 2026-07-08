import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
} from "amazon-cognito-identity-js";

import { loadConfig } from "@/lib/config";

const TOKEN_KEY = "book.idToken";

// NEW_PASSWORD_REQUIRED is thrown when a freshly created user must set their own password.
export const NEW_PASSWORD_REQUIRED = "NEW_PASSWORD_REQUIRED";

let idToken: string | null = null;

function readStored(): string | null {
  if (idToken) return idToken;
  try {
    idToken = sessionStorage.getItem(TOKEN_KEY);
  } catch {
    idToken = null;
  }
  return idToken;
}

function store(token: string): void {
  idToken = token;
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Session storage may be unavailable; the token stays in memory for the session.
  }
}

export function getIdToken(): string | null {
  return readStored();
}

export function isAuthenticated(): boolean {
  return getIdToken() !== null;
}

export function signOut(): void {
  idToken = null;
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to clear.
  }
}

// End an expired or revoked session: clear the token and return the user to the login page,
// unless they are already there (nothing on /login calls the API, so there is no loop).
export function endSession(): void {
  signOut();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.assign("/login");
  }
}

async function userPool(): Promise<CognitoUserPool> {
  const config = await loadConfig();
  if (!config.cognitoUserPoolId || !config.cognitoClientId) {
    throw new Error("Auth is not configured for this environment.");
  }
  return new CognitoUserPool({
    UserPoolId: config.cognitoUserPoolId,
    ClientId: config.cognitoClientId,
  });
}

// Sign in and store the id token. On a first login with a temporary password Cognito requires
// a new password; without one this rejects with NEW_PASSWORD_REQUIRED so the caller can prompt.
export async function signIn(
  email: string,
  password: string,
  newPassword?: string,
): Promise<void> {
  const user = new CognitoUser({ Username: email, Pool: await userPool() });
  const details = new AuthenticationDetails({ Username: email, Password: password });
  await new Promise<void>((resolve, reject) => {
    user.authenticateUser(details, {
      onSuccess: (session) => {
        store(session.getIdToken().getJwtToken());
        resolve();
      },
      onFailure: reject,
      newPasswordRequired: () => {
        if (!newPassword) {
          reject(new Error(NEW_PASSWORD_REQUIRED));
          return;
        }
        user.completeNewPasswordChallenge(newPassword, {}, {
          onSuccess: (session) => {
            store(session.getIdToken().getJwtToken());
            resolve();
          },
          onFailure: reject,
        });
      },
    });
  });
}
