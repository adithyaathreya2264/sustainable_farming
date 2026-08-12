import React from "react";
import { Text, TextInput, View, type TextInputProps } from "react-native";

interface TextFieldProps extends TextInputProps {
  label: string;
}

export function TextField({ label, style, ...props }: TextFieldProps) {
  return (
    <View className="mb-4">
      <Text className="text-ink-muted mb-1.5" style={{ fontSize: 14 }}>
        {label}
      </Text>
      <TextInput
        accessibilityLabel={label}
        className="rounded-xl border border-border bg-surface px-4 text-ink"
        style={[{ minHeight: 48, fontSize: 16 }, style]}
        placeholderTextColor="#9AA39A"
        {...props}
      />
    </View>
  );
}

export function NumericField(props: TextFieldProps) {
  return <TextField keyboardType="numeric" {...props} />;
}
