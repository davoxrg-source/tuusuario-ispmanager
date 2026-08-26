import { Tabs } from "expo-router";

export default function AppLayout() {
  return (
    <Tabs screenOptions={{ headerTitleAlign: "center" }}>
      <Tabs.Screen name="index" options={{ title: "Inicio" }} />
      <Tabs.Screen name="facturas" options={{ title: "Facturas" }} />
    </Tabs>
  );
}
