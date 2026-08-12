import { Redirect } from "expo-router";
import { useSession } from "../context/SessionContext";

export default function Index() {
  const { isAuthenticated, user } = useSession();

  if (!isAuthenticated) {
    return <Redirect href="/(auth)/login" />;
  }
  if (!user.onboardingComplete) {
    return <Redirect href="/(onboarding)/step-1" />;
  }
  return <Redirect href="/(tabs)/home" />;
}
