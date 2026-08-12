import React from "react";
import {
  ActivityIndicator,
  Pressable,
  Text,
  type PressableProps,
} from "react-native";

type Variant = "primary" | "secondary" | "danger" | "outline";

interface ButtonProps extends Omit<PressableProps, "children"> {
  label: string;
  variant?: Variant;
  loading?: boolean;
  fullWidth?: boolean;
}

const VARIANT_STYLES: Record<Variant, { bg: string; text: string; border?: string }> = {
  primary: { bg: "bg-primary", text: "text-white" },
  danger: { bg: "bg-danger", text: "text-white" },
  secondary: { bg: "bg-info", text: "text-white" },
  outline: { bg: "bg-transparent border border-primary", text: "text-primary" },
};

export function Button({
  label,
  variant = "primary",
  loading = false,
  fullWidth = true,
  disabled,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;
  const style = VARIANT_STYLES[variant];

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: isDisabled }}
      disabled={isDisabled}
      className={`${style.bg} ${fullWidth ? "w-full" : ""} rounded-xl items-center justify-center px-6`}
      style={[{ minHeight: 48, opacity: isDisabled ? 0.5 : 1 }]}
      {...props}
    >
      {loading ? (
        <ActivityIndicator color={variant === "outline" ? "#2E7D32" : "#FFFFFF"} />
      ) : (
        <Text className={`${style.text} font-semibold`} style={{ fontSize: 16 }}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}
