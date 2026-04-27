/**
 * Auth removed for personal-use FundAgent.
 * This file remains as a stub for legacy imports that haven't been cleaned up.
 */

export interface User {
  user_id: string;
  username: string;
  is_admin: boolean;
}

export const authStorage = {
  getToken(): string | null {
    return null;
  },
  getAccessToken(): string | null {
    return null;
  },
  getRefreshToken(): string | null {
    return null;
  },
  getUser(): User | null {
    return { user_id: "local", username: "local", is_admin: true };
  },
  clear(): void {},
};

export async function logout(): Promise<void> {}
