import React from "react";
import { ScrollView, View, type ViewProps } from "react-native";
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
  const Wrapper = scroll ? ScrollView : View;
  const wrapperProps: ViewProps & { contentContainerStyle?: object } = scroll
    ? { contentContainerStyle: { paddingBottom: 32 } }
    : { style: { flex: 1 } };

  return (
    <SafeAreaView className={`flex-1 bg-background ${className}`} edges={["top"]}>
      <Wrapper className={`px-4 pt-4 ${contentClassName}`} {...wrapperProps}>
        {children}
      </Wrapper>
    </SafeAreaView>
  );
}
