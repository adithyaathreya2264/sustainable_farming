import React, { useState } from "react";
import { Pressable, Text } from "react-native";
import { useTranslation } from "react-i18next";
import { NumericField } from "./ui/TextField";
import type { SoilTestInput } from "../services/fields";
import type { SoilCardValue } from "../services/ml";

/**
 * Soil-test card entry, shared by add-field and add-soil-test. The four basic
 * values are always shown; the other eight (needed only for the fertility
 * class, model 5b) sit behind "More values from your soil-test card" so a
 * farmer with only N/P/K/pH is not faced with twelve boxes.
 */
export type SoilTestValues = Partial<Record<SoilCardValue, string>>;

export const BASIC_VALUES: SoilCardValue[] = ["nitrogen", "phosphorus", "potassium", "ph"];
export const CARD_VALUES: SoilCardValue[] = [
  "ec", "organic_carbon", "sulphur", "zinc", "iron", "copper", "manganese", "boron",
];

export function hasAnySoilValue(values: SoilTestValues): boolean {
  return Object.values(values).some((v) => v !== undefined && v !== "");
}

export function toSoilTestInput(values: SoilTestValues): SoilTestInput {
  const n = (k: SoilCardValue) => (values[k] ? Number(values[k]) : null);
  return {
    nitrogen: n("nitrogen"),
    phosphorus: n("phosphorus"),
    potassium: n("potassium"),
    ph: n("ph"),
    ec: n("ec"),
    organicCarbon: n("organic_carbon"),
    sulphur: n("sulphur"),
    zinc: n("zinc"),
    iron: n("iron"),
    copper: n("copper"),
    manganese: n("manganese"),
    boron: n("boron"),
  };
}

export function SoilTestFields({
  values,
  onChange,
  startExpanded = false,
}: {
  values: SoilTestValues;
  onChange: (next: SoilTestValues) => void;
  startExpanded?: boolean;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(startExpanded);
  const field = (key: SoilCardValue) => (
    <NumericField
      key={key}
      label={t(`soilTest.value.${key}`)}
      placeholder="0"
      value={values[key] ?? ""}
      onChangeText={(v) => onChange({ ...values, [key]: v.replace(/[^0-9.]/g, "") })}
    />
  );

  return (
    <>
      {BASIC_VALUES.map(field)}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        onPress={() => setExpanded((e) => !e)}
        className="mb-3"
        style={{ minHeight: 44, justifyContent: "center" }}
      >
        <Text className="text-primary font-semibold" style={{ fontSize: 14 }}>
          {expanded ? "▲ " : "▼ "}
          {t("soilTest.moreValues")}
        </Text>
        <Text className="text-ink-muted" style={{ fontSize: 12 }}>
          {t("soilTest.moreValuesHint")}
        </Text>
      </Pressable>
      {expanded && CARD_VALUES.map(field)}
    </>
  );
}
