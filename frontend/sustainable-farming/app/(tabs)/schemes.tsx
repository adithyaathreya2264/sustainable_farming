import React, { useCallback, useState } from "react";
import { Text } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { EmptyState } from "../../components/ui/EmptyState";
import { SkeletonCard } from "../../components/ui/SkeletonLoader";
import { SchemeCard } from "../../components/SchemeCard";
import { getMatchedSchemes } from "../../services/schemes";
import type { Scheme } from "../../types/models";

export default function SchemesScreen() {
  const { t } = useTranslation();
  const [schemes, setSchemes] = useState<Scheme[] | null>(null);

  useFocusEffect(
    useCallback(() => {
      getMatchedSchemes().then(setSchemes);
    }, [])
  );

  return (
    <ScreenContainer>
      <Text className="text-ink font-bold mb-4" style={{ fontSize: 22 }}>
        {t("schemes.title")}
      </Text>

      {schemes === null ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : schemes.length === 0 ? (
        <EmptyState
          icon="📜"
          title={t("schemes.noSchemesTitle")}
          subtitle={t("schemes.noSchemesSubtitle")}
        />
      ) : (
        schemes.map((scheme) => (
          <SchemeCard
            key={scheme.id}
            scheme={scheme}
            onPress={() => router.push(`/scheme/${scheme.id}`)}
          />
        ))
      )}
    </ScreenContainer>
  );
}
