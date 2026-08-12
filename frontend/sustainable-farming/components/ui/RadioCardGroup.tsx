import React from "react";
import { Pressable, Text, View } from "react-native";

export interface RadioCardOption<T extends string> {
  value: T;
  label: string;
  icon?: string;
}

interface RadioCardGroupProps<T extends string> {
  options: RadioCardOption<T>[];
  value: T | undefined;
  onChange: (value: T) => void;
  columns?: 1 | 2;
}

export function RadioCardGroup<T extends string>({
  options,
  value,
  onChange,
  columns = 2,
}: RadioCardGroupProps<T>) {
  return (
    <View className="flex-row flex-wrap -mx-1">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <View key={option.value} style={{ width: columns === 2 ? "50%" : "100%" }} className="p-1">
            <Pressable
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={option.label}
              onPress={() => onChange(option.value)}
              className={`rounded-xl border-2 items-center justify-center px-3 ${
                selected ? "border-primary bg-primary/10" : "border-border bg-surface"
              }`}
              style={{ minHeight: 64, paddingVertical: 12 }}
            >
              {option.icon ? (
                <Text style={{ fontSize: 24 }}>{option.icon}</Text>
              ) : null}
              <Text
                className={`text-center font-medium ${selected ? "text-primary-dark" : "text-ink"}`}
                style={{ fontSize: 15, marginTop: option.icon ? 4 : 0 }}
              >
                {option.label}
              </Text>
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}
