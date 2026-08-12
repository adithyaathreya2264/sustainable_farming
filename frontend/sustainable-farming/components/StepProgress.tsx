import React from "react";
import { View } from "react-native";

export function StepProgress({ step, total }: { step: number; total: number }) {
  return (
    <View className="flex-row mb-6" accessibilityLabel={`Step ${step} of ${total}`}>
      {Array.from({ length: total }).map((_, index) => (
        <View
          key={index}
          className={`flex-1 rounded-full mx-1 ${
            index < step ? "bg-primary" : "bg-border"
          }`}
          style={{ height: 4 }}
        />
      ))}
    </View>
  );
}
