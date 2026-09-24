import React from "react";
import { useTranslation } from "react-i18next";
import { CaveatText } from "../ui/CaveatText";

/** One line under every model result: none of this is agronomist-reviewed. */
export function ModelNotice() {
  const { t } = useTranslation();
  return <CaveatText className="mt-2">{t("ml.modelNotice")}</CaveatText>;
}
