import React, { useState } from "react";
import { Text } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Button } from "../../components/ui/Button";
import {
  hasAnySoilValue,
  SoilTestFields,
  toSoilTestInput,
  type SoilTestValues,
} from "../../components/SoilTestFields";
import { useToast } from "../../context/ToastContext";
import { useAppState } from "../../hooks/useAppState";
import { addSoilTest } from "../../services/fields";

/**
 * Enter a soil-test card for an existing field. It becomes the field's
 * current test, used by crop recommendation, the nutrient check and the
 * fertility class. Opened from the ledger's soil-fertility card.
 */
export default function AddSoilTestModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { fieldId, expand } = useLocalSearchParams<{ fieldId: string; expand?: string }>();
  const field = useAppState((s) => s.fields.find((f) => f.id === fieldId));
  const [values, setValues] = useState<SoilTestValues>({});
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await addSoilTest(fieldId, toSoilTestInput(values));
      showToast(t("common.saved"));
      router.back();
    } catch {
      showToast(t("common.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("soilTest.title")} />
      {field && (
        <Text className="text-ink-muted mb-1" style={{ fontSize: 14 }}>
          {field.name}
        </Text>
      )}
      <Text className="text-ink-muted mb-4" style={{ fontSize: 13 }}>
        {t("soilTest.hint")}
      </Text>
      <SoilTestFields values={values} onChange={setValues} startExpanded={expand === "1"} />
      <Button label={t("common.save")} disabled={!hasAnySoilValue(values)} loading={saving} onPress={handleSave} />
    </ScreenContainer>
  );
}
