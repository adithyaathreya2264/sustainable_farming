import { apiFetch } from "../lib/apiClient";
import { getState, markLiveSession, setState } from "../store/appStore";
import { fetchProfile } from "./users";

/**
 * Real calls to the backend's phone+OTP auth (backend/api/v1/auth.py — see
 * the "Background Data Sync" plan section for the verified contract).
 * Signatures/return shapes are kept identical to the mock this replaced so
 * app/(auth)/login.tsx and otp.tsx needed no changes.
 */

export async function requestOtp(phoneNumber: string): Promise<{ sent: true }> {
  setState({ user: { ...getState().user, phoneNumber } });
  try {
    await apiFetch("/api/v1/auth/request-otp", {
      method: "POST",
      body: { phone_number: phoneNumber },
      skipAuth: true,
    });
  } catch {
    // Degrade quietly — the OTP screen doesn't distinguish "not sent" from
    // "sent but slow"; a resend is always available if it never arrives.
  }
  return { sent: true };
}

export interface VerifyOtpResult {
  success: boolean;
  isNewUser: boolean;
}

interface VerifyOtpResponse {
  access_token: string;
  token_type: string;
}

export async function verifyOtp(otp: string): Promise<VerifyOtpResult> {
  const phoneNumber = getState().user.phoneNumber;
  try {
    const res = await apiFetch<VerifyOtpResponse>("/api/v1/auth/verify-otp", {
      method: "POST",
      body: { phone_number: phoneNumber, otp },
      skipAuth: true,
    });
    setState({ isAuthenticated: true, authToken: res.access_token });
    // Promote the local dataset to "live" (and clear any demo rows) before the
    // first sync so mock records can never be pushed to the backend.
    markLiveSession();
    // Hydrate the real profile (id, onboarding_complete, any saved fields) so
    // `user.id` stops being the mock "u1" and returning users skip onboarding.
    // Best-effort: if it fails, fall back to the local onboarding flag.
    const profile = await fetchProfile();
    const isNewUser = profile
      ? !profile.onboardingComplete
      : !getState().user.onboardingComplete;
    return { success: true, isNewUser };
  } catch {
    // Covers both the backend's real 401 "Invalid or expired credentials."
    // and any network failure — both degrade to the OTP screen's existing
    // generic "incorrect code" messaging.
    return { success: false, isNewUser: false };
  }
}
