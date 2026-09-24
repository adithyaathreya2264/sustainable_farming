import React from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import type { PhotoSource } from "../../lib/photo";

/** "Take photo" / "Choose photo" pair for starting a model photo check. */
export function PhotoSourceButtons({
  label,
  busy = false,
  disabled = false,
  onPick,
}: {
  label?: string;
  busy?: boolean;
  disabled?: boolean;
  onPick: (source: PhotoSource) => void;
}) {
  const { t } = useTranslation();
  const off = busy || disabled;
  return (
    <View className="mb-3">
      {label ? (
        <Text className="text-ink font-semibold mb-2" style={{ fontSize: 14 }}>
          {label}
        </Text>
      ) : null}
      <View className="flex-row" style={{ gap: 8 }}>
        {(["camera", "library"] as const).map((source) => (
          <Pressable
            key={source}
            accessibilityRole="button"
            disabled={off}
            onPress={() => onPick(source)}
            className={`flex-1 rounded-xl border border-primary items-center justify-center ${off ? "opacity-50" : ""}`}
            style={{ minHeight: 48 }}
          >
            <Text className="text-primary font-semibold" style={{ fontSize: 14 }}>
              {source === "camera" ? `📷 ${t("ml.takePhoto")}` : `🖼️ ${t("ml.choosePhoto")}`}
            </Text>
          </Pressable>
        ))}
      </View>
      {busy && (
        <View className="flex-row items-center mt-2" style={{ gap: 8 }}>
          <ActivityIndicator color="#2E7D32" />
          <Text className="text-ink-muted" style={{ fontSize: 13 }}>
            {t("ml.checking")}
          </Text>
        </View>
      )}
    </View>
  );
}
