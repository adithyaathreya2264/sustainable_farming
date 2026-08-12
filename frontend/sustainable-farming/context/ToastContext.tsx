import React, { createContext, useCallback, useContext, useState } from "react";
import { Text, View } from "react-native";
import { colors } from "../theme";

interface ToastContextValue {
  showToast: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(null), 2200);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {message && (
        <View
          className="absolute bottom-24 left-4 right-4 items-center"
          pointerEvents="none"
        >
          <View
            className="rounded-full px-5 py-3"
            style={{ backgroundColor: colors.ink }}
          >
            <Text className="text-white text-center" style={{ fontSize: 15 }}>
              {message}
            </Text>
          </View>
        </View>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
