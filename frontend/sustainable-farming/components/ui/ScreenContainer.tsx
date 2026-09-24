import React from "react";
import { KeyboardAvoidingView, Platform, ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

interface ScreenContainerProps {
  children: React.ReactNode;
  scroll?: boolean;
  className?: string;
  contentClassName?: string;
}

export function ScreenContainer({
  children,
  scroll = true,
  className = "",
  contentClassName = "",
}: ScreenContainerProps) {
  // Always a ScrollView, even for `scroll={false}` screens (login/OTP): those
  // just start centered via flexGrow, but still need to be scrollable so the
  // keyboard can push content further up than KeyboardAvoidingView alone
  // manages — see app.json's android.softwareKeyboardLayoutMode: "pan",
  // which hands keyboard layout entirely to KeyboardAvoidingView instead of
  // Android's own resize (the two fighting each other is what caused inputs
  // to stay hidden behind the keyboard).
  return (
    <SafeAreaView className={`flex-1 bg-background ${className}`} edges={["top"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <ScrollView
          className={`px-4 pt-4 ${contentClassName}`}
          contentContainerStyle={scroll ? { paddingBottom: 32 } : { flexGrow: 1, paddingBottom: 32 }}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
        >
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
