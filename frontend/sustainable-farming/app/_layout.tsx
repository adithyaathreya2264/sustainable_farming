import "../global.css";
import "../lib/i18n";
import React, { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { AnimatedSplash } from "../components/AnimatedSplash";
import { SessionProvider } from "../context/SessionContext";
import { LanguageProvider } from "../context/LanguageContext";
import { ToastProvider } from "../context/ToastContext";
import { hydrate } from "../store/appStore";
import { useAppState } from "../hooks/useAppState";
import { useRefreshTriggers } from "../hooks/useRefreshTriggers";

// Keep the native splash up until AnimatedSplash has drawn the same logo.
SplashScreen.preventAutoHideAsync().catch(() => {});

function AppShell() {
  const hydrated = useAppState((s) => s.hydrated);
  const [splashDone, setSplashDone] = useState(false);

  useEffect(() => {
    hydrate();
  }, []);

  useRefreshTriggers();

  const hideNativeSplash = useCallback(() => {
    SplashScreen.hideAsync().catch(() => {});
  }, []);
  const finishSplash = useCallback(() => setSplashDone(true), []);

  return (
    <View style={{ flex: 1 }}>
      <StatusBar style={splashDone ? "dark" : "light"} />
      {hydrated && <AppContent />}
      {!splashDone && (
        <AnimatedSplash ready={hydrated} onLogoReady={hideNativeSplash} onFinish={finishSplash} />
      )}
    </View>
  );
}

function AppContent() {
  return (
    <LanguageProvider>
      <ToastProvider>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="(auth)" />
          <Stack.Screen name="(onboarding)" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen
            name="modals/add-field"
            options={{ presentation: "modal", headerShown: false }}
          />
          <Stack.Screen
            name="modals/add-planting"
            options={{ presentation: "modal", headerShown: false }}
          />
          <Stack.Screen
            name="modals/quick-log"
            options={{ presentation: "modal", headerShown: false }}
          />
          <Stack.Screen
            name="modals/log-scouting"
            options={{ presentation: "modal", headerShown: false }}
          />
          <Stack.Screen
            name="modals/add-soil-test"
            options={{ presentation: "modal", headerShown: false }}
          />
          <Stack.Screen name="alert/[id]" options={{ headerShown: false }} />
          <Stack.Screen name="scheme/[id]" options={{ headerShown: false }} />
          <Stack.Screen
            name="ledger/[plantingId]"
            options={{ headerShown: false }}
          />
          <Stack.Screen name="planting/[plantingId]/photo-check" options={{ headerShown: false }} />
          <Stack.Screen name="planting/[plantingId]/diseases" options={{ headerShown: false }} />
          <Stack.Screen name="market" options={{ headerShown: false }} />
          <Stack.Screen name="photo-history" options={{ headerShown: false }} />
        </Stack>
      </ToastProvider>
    </LanguageProvider>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <SessionProvider>
          <AppShell />
        </SessionProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
