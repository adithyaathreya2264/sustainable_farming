import { Redirect } from "expo-router";

// Unreachable in practice: the tab bar intercepts presses on this tab via
// `tabPress` in the Tabs layout and pushes the Quick Log modal instead.
export default function LogPlaceholder() {
  return <Redirect href="/(tabs)/home" />;
}
