import React from "react";
import { FlatList, Modal, Pressable, Text, View } from "react-native";
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
}

export function BottomSheetPicker({
  visible,
  title,
  options,
  selectedValue,
  onSelect,
  onClose,
}: BottomSheetPickerProps) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable className="flex-1 bg-black/40" onPress={onClose} />
      <SafeAreaView edges={["bottom"]} className="bg-surface rounded-t-3xl max-h-[70%]">
        <View className="px-5 pt-4 pb-2 border-b border-border">
          <Text className="text-lg font-semibold text-ink">{title}</Text>
        </View>
        <FlatList
          data={options}
          keyExtractor={(item) => item.value}
          renderItem={({ item }) => {
            const selected = item.value === selectedValue;
            return (
              <Pressable
                accessibilityRole="button"
                onPress={() => {
                  onSelect(item.value);
                  onClose();
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
