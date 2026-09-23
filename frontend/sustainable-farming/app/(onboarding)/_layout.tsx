import { Stack } from "expo-router";
import { OnboardingDraftProvider } from "../../context/OnboardingDraftContext";

export default function OnboardingLayout() {
  return (
    <OnboardingDraftProvider>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="step-1" />
        <Stack.Screen name="step-2" />
        <Stack.Screen name="step-3" />
        <Stack.Screen name="step-4" />
        <Stack.Screen name="step-5" />
      </Stack>
    </OnboardingDraftProvider>
  );
}
