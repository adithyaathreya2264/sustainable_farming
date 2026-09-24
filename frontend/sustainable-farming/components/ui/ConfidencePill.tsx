import React from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import type { ConfidenceLabel } from "../../types/models";

/** The categorical confidence label as a pill. No model score is ever shown -
 * the label is all the backend sends (ml/README.md rule 1). */
export function ConfidencePill({
  label,
  className = "bg-ink-muted",
}: {
  label: ConfidenceLabel;
  /** Background class; defaults to a neutral grey. */
  className?: string;
}) {
  const { t } = useTranslation();
  return (
    <View className={`${className} rounded-full px-2.5 py-0.5 self-start`}>
      <Text className="text-white" style={{ fontSize: 12 }}>
        {t(`confidence.${label}`)}
      </Text>
    </View>
  );
}
