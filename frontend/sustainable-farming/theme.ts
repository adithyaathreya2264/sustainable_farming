/**
 * Design tokens mirrored from tailwind.config.js, for places that need raw
 * values instead of className strings (icon colors, StatusBar, charts).
 */
export const colors = {
  primary: "#2E7D32",
  primaryDark: "#1B5E20",
  primaryLight: "#66BB6A",
  danger: "#D32F2F",
  dangerLight: "#EF5350",
  info: "#1976D2",
  infoLight: "#42A5F5",
  background: "#F5F5F5",
  surface: "#FFFFFF",
  ink: "#1A1A1A",
  inkMuted: "#5F6B5F",
  border: "#E0E0E0",
} as const;

export const spacing = {
  screenPadding: 16,
} as const;

export const minTouchTarget = 48;
