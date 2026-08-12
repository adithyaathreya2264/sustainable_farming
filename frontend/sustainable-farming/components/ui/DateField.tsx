import React, { useState } from "react";
import { Platform } from "react-native";
import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { PickerField } from "./BottomSheetPicker";
import { formatDate } from "../../utils/format";

interface DateFieldProps {
  label: string;
  value: string; // ISO date
  onChange: (isoDate: string) => void;
  maximumDate?: Date;
}

export function DateField({ label, value, onChange, maximumDate }: DateFieldProps) {
  const [open, setOpen] = useState(false);

  function handleChange(event: DateTimePickerEvent, date?: Date) {
    setOpen(Platform.OS === "ios");
    if (event.type === "set" && date) {
      onChange(date.toISOString().slice(0, 10));
    }
  }

  return (
    <>
      <PickerField
        label={label}
        placeholder={label}
        displayValue={formatDate(value)}
        onPress={() => setOpen(true)}
      />
      {open && (
        <DateTimePicker
          value={new Date(value)}
          mode="date"
          display={Platform.OS === "ios" ? "inline" : "default"}
          maximumDate={maximumDate}
          onChange={handleChange}
        />
      )}
    </>
  );
}
