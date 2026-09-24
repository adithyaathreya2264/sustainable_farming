import React, { useMemo, useState } from "react";
import { FlatList, Modal, Pressable, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

export interface PickerOption {
  label: string;
  value: string;
}

interface BottomSheetPickerProps {
  visible: boolean;
  title: string;
  options: PickerOption[];
  selectedValue?: string;
  onSelect: (value: string) => void;
  onClose: () => void;
  /** Adds a search box at the top of the sheet that filters `options` by label. */
  searchable?: boolean;
  searchPlaceholder?: string;
}

export function BottomSheetPicker({
  visible,
  title,
  options,
  selectedValue,
  onSelect,
  onClose,
  searchable = false,
  searchPlaceholder,
}: BottomSheetPickerProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!searchable || !query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query, searchable]);

  function handleClose() {
    setQuery("");
    onClose();
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={handleClose}>
      <Pressable className="flex-1 bg-black/40" onPress={handleClose} />
      <SafeAreaView edges={["bottom"]} className="bg-surface rounded-t-3xl max-h-[70%]">
        <View className="px-5 pt-4 pb-2 border-b border-border">
          <Text className="text-lg font-semibold text-ink">{title}</Text>
        </View>
        {searchable && (
          <View className="px-5 pt-3 pb-1">
            <TextInput
              accessibilityLabel={searchPlaceholder ?? title}
              value={query}
              onChangeText={setQuery}
              placeholder={searchPlaceholder}
              placeholderTextColor="#9AA39A"
              autoCorrect={false}
              className="rounded-xl border border-border bg-background px-4 text-ink"
              style={{ minHeight: 44, fontSize: 15 }}
            />
          </View>
        )}
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.value}
          keyboardShouldPersistTaps="handled"
          renderItem={({ item }) => {
            const selected = item.value === selectedValue;
            return (
              <Pressable
                accessibilityRole="button"
                onPress={() => {
                  onSelect(item.value);
                  handleClose();
                }}
                className={`px-5 py-4 border-b border-border ${selected ? "bg-primary/10" : ""}`}
                style={{ minHeight: 48, justifyContent: "center" }}
              >
                <Text
                  className={selected ? "text-primary-dark font-semibold" : "text-ink"}
                  style={{ fontSize: 16 }}
                >
                  {item.label}
                </Text>
              </Pressable>
            );
          }}
          ListEmptyComponent={
            searchable ? (
              <View className="px-5 py-6">
                <Text className="text-ink-muted" style={{ fontSize: 14 }}>
                  No matches.
                </Text>
              </View>
            ) : null
          }
        />
      </SafeAreaView>
    </Modal>
  );
}

interface PickerFieldProps {
  label: string;
  placeholder: string;
  value?: string;
  displayValue?: string;
  disabled?: boolean;
  onPress: () => void;
}

export function PickerField({
  label,
  placeholder,
  displayValue,
  disabled,
  onPress,
}: PickerFieldProps) {
  return (
    <View className="mb-4">
      <Text className="text-ink-muted mb-1.5" style={{ fontSize: 14 }}>
        {label}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        disabled={disabled}
        onPress={onPress}
        className="rounded-xl border border-border bg-surface px-4 justify-center"
        style={{ minHeight: 48, opacity: disabled ? 0.5 : 1 }}
      >
        <Text style={{ fontSize: 16 }} className={displayValue ? "text-ink" : "text-ink-muted"}>
          {displayValue ?? placeholder}
        </Text>
      </Pressable>
    </View>
  );
}
