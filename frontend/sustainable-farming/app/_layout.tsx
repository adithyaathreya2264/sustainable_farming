import "../global.css";
import "../lib/i18n";
import React, { useEffect, useState } from "react";
import { View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SessionProvider } from "../context/SessionContext";
import { LanguageProvider } from "../context/LanguageContext";
import { ToastProvider } from "../context/ToastContext";
import { hydrate } from "../store/appStore";
import { useAppState } from "../hooks/useAppState";
import { useRefreshTriggers } from "../hooks/useRefreshTriggers";
import { colors } from "../theme";

function AppShell() {
  const hydrated = useAppState((s) => s.hydrated);

  useEffect(() => {
    hydrate();
  }, []);

  useRefreshTriggers();

  if (!hydrated) {
    return <View style={{ flex: 1, backgroundColor: colors.background }} />;
  }

  return (
    <LanguageProvider>
      <ToastProvider>
        <StatusBar style="dark" />
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
