import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { fetchMyProfile } from "../../src/api/auth";
import { useAuth } from "../../src/auth/AuthContext";

const statusLabels: Record<string, string> = {
  active: "Activo",
  suspended: "Suspendido",
  cancelled: "Cancelado",
};

export default function Dashboard() {
  const { signOut } = useAuth();
  const { data: profile, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["my-profile"],
    queryFn: fetchMyProfile,
  });

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
    >
      <Text style={styles.name}>{profile?.full_name}</Text>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Estado</Text>
        <Text style={styles.cardValue}>{statusLabels[profile?.status ?? ""] ?? "—"}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Conectividad</Text>
        <Text style={styles.cardValue}>{profile?.is_online ? "En línea" : "Sin conexión"}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Saldo a favor</Text>
        <Text style={styles.cardValue}>${Number(profile?.pending_credit ?? 0).toFixed(2)}</Text>
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={() => signOut()}>
        <Text style={styles.logoutText}>Cerrar sesión</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  container: { padding: 16 },
  name: { fontSize: 20, fontWeight: "700", color: "#0f172a", marginBottom: 16 },
  card: {
    backgroundColor: "#f8fafc",
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cardLabel: { fontSize: 12, color: "#64748b" },
  cardValue: { fontSize: 18, fontWeight: "600", color: "#0f172a", marginTop: 4 },
  logoutButton: { marginTop: 24, alignItems: "center", padding: 12 },
  logoutText: { color: "#dc2626", fontWeight: "600" },
});
