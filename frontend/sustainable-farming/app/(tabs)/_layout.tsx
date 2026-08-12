import React from "react";
import { Pressable, Text, View } from "react-native";
import { Tabs, router } from "expo-router";
import { useTranslation } from "react-i18next";
import { colors, minTouchTarget } from "../../theme";

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return (
    <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.55 }}>{emoji}</Text>
  );
}

function TabLabel({ label, focused }: { label: string; focused: boolean }) {
  return (
    <Text
      style={{
        fontSize: 11,
        color: focused ? colors.primary : colors.inkMuted,
        fontWeight: focused ? "600" : "400",
      }}
    >
      {label}
    </Text>
  );
}

function FabButton() {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Log new activity"
      onPress={() => router.push("/modals/quick-log")}
      style={{
        top: -18,
        alignSelf: "center",
        width: minTouchTarget + 8,
        height: minTouchTarget + 8,
        borderRadius: (minTouchTarget + 8) / 2,
        backgroundColor: colors.primary,
        alignItems: "center",
        justifyContent: "center",
        shadowColor: "#000",
        shadowOpacity: 0.2,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 3 },
        elevation: 4,
      }}
    >
      <Text style={{ fontSize: 28, color: "white", marginTop: -2 }}>+</Text>
    </Pressable>
  );
}

export default function TabsLayout() {
  const { t } = useTranslation();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarStyle: { height: 64, paddingTop: 6, paddingBottom: 10 },
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: "Home",
          tabBarIcon: ({ focused }) => <TabIcon emoji="🏠" focused={focused} />,
          tabBarLabel: ({ focused }) => <TabLabel label="Home" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="fields"
        options={{
          title: t("fields.title"),
          tabBarIcon: ({ focused }) => <TabIcon emoji="🌾" focused={focused} />,
          tabBarLabel: ({ focused }) => (
            <TabLabel label={t("fields.title")} focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        name="log"
        options={{
          title: "",
          tabBarLabel: () => <View />,
          tabBarIcon: () => <FabButton />,
        }}
        listeners={{
          tabPress: (e) => {
            e.preventDefault();
            router.push("/modals/quick-log");
          },
        }}
      />
      <Tabs.Screen
        name="schemes"
        options={{
          title: t("schemes.title"),
          tabBarIcon: ({ focused }) => <TabIcon emoji="📜" focused={focused} />,
          tabBarLabel: ({ focused }) => (
            <TabLabel label={t("schemes.title")} focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: t("profile.title"),
          tabBarIcon: ({ focused }) => <TabIcon emoji="👤" focused={focused} />,
          tabBarLabel: ({ focused }) => (
            <TabLabel label={t("profile.title")} focused={focused} />
          ),
        }}
      />
    </Tabs>
  );
}
