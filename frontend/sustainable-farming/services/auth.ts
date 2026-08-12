import { getState, setState } from "../store/appStore";

/**
 * Mocks the FastAPI `/api/v1/auth/request-otp` and `/verify-otp` endpoints
 * (MSG91-backed in production). The fixed code keeps the flow demoable
 * without a real SMS provider.
 */
export const MOCK_OTP = "123456";

export async function requestOtp(phoneNumber: string): Promise<{ sent: true }> {
  await delay(600);
  setState({ user: { ...getState().user, phoneNumber } });
  return { sent: true };
}

export interface VerifyOtpResult {
  success: boolean;
  isNewUser: boolean;
}

export async function verifyOtp(otp: string): Promise<VerifyOtpResult> {
  await delay(600);
  if (otp !== MOCK_OTP) {
    return { success: false, isNewUser: false };
  }
  setState({ isAuthenticated: true });
  return { success: true, isNewUser: !getState().user.onboardingComplete };
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
