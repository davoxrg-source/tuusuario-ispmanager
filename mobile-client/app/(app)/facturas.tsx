import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Linking from "expo-linking";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { createCheckoutUrl, listMyInvoices, reportPayment } from "../../src/api/portal";
import type { Invoice } from "../../src/api/types";

const statusLabels: Record<string, string> = {
  pending: "Pendiente",
  paid: "Pagada",
  overdue: "Vencida",
  cancelled: "Cancelada",
};

const statusColors: Record<string, string> = {
  pending: "#64748b",
  paid: "#16a34a",
  overdue: "#dc2626",
  cancelled: "#94a3b8",
};

export default function Facturas() {
  const queryClient = useQueryClient();
  const {
    data: invoices = [],
    isLoading,
    refetch,
    isRefetching,
  } = useQuery({ queryKey: ["my-invoices"], queryFn: listMyInvoices });
  const [reportingInvoice, setReportingInvoice] = useState<Invoice | null>(null);
  const [method, setMethod] = useState("");
  const [reference, setReference] = useState("");

  const checkoutMutation = useMutation({
    mutationFn: createCheckoutUrl,
    onSuccess: (result) => Linking.openURL(result.checkout_url),
    onError: () => Alert.alert("No se pudo iniciar el pago en línea. Probá de nuevo en un momento."),
  });

  const reportMutation = useMutation({
    mutationFn: (invoice: Invoice) =>
      reportPayment({ invoice_id: invoice.id, amount: invoice.amount, method, reference: reference || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-invoices"] });
      setReportingInvoice(null);
      setMethod("");
      setReference("");
      Alert.alert("Pago reportado", "El staff va a revisarlo y confirmarlo.");
    },
    onError: () => Alert.alert("No se pudo reportar el pago."),
  });

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <>
      <FlatList
        contentContainerStyle={styles.list}
        data={invoices}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.folio}>{item.folio ?? "Sin folio"}</Text>
              <Text style={[styles.status, { color: statusColors[item.status] }]}>
                {statusLabels[item.status]}
              </Text>
            </View>
            <Text style={styles.amount}>${Number(item.amount).toFixed(2)}</Text>
            <Text style={styles.due}>Vence: {item.due_date}</Text>

            {(item.status === "pending" || item.status === "overdue") && (
              <View style={styles.actions}>
                <TouchableOpacity
                  style={styles.payButton}
                  onPress={() => checkoutMutation.mutate(item.id)}
                  disabled={checkoutMutation.isPending}
                >
                  <Text style={styles.payButtonText} numberOfLines={1}>
                    Pagar en línea
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.reportButton} onPress={() => setReportingInvoice(item)}>
                  <Text style={styles.reportButtonText} numberOfLines={1}>
                    Ya pagué
                  </Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No tenés facturas todavía.</Text>}
      />

      <Modal visible={reportingInvoice !== null} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Reportar pago</Text>
            <TextInput
              style={styles.input}
              placeholder="Método (ej. Nequi, transferencia)"
              value={method}
              onChangeText={setMethod}
            />
            <TextInput
              style={styles.input}
              placeholder="Referencia (opcional)"
              value={reference}
              onChangeText={setReference}
            />
            <TouchableOpacity
              style={styles.payButton}
              onPress={() => reportingInvoice && reportMutation.mutate(reportingInvoice)}
              disabled={!method || reportMutation.isPending}
            >
              <Text style={styles.payButtonText}>Confirmar</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setReportingInvoice(null)}>
              <Text style={styles.cancelButtonText}>Cancelar</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  list: { padding: 16 },
  card: {
    backgroundColor: "#f8fafc",
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between" },
  folio: { fontSize: 13, color: "#64748b" },
  status: { fontSize: 13, fontWeight: "600" },
  amount: { fontSize: 22, fontWeight: "700", color: "#0f172a", marginTop: 4 },
  due: { fontSize: 13, color: "#64748b", marginTop: 2 },
  actions: { gap: 8, marginTop: 12 },
  payButton: {
    backgroundColor: "#0f172a",
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 8,
    alignItems: "center",
  },
  payButtonText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  reportButton: {
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 8,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#0f172a",
  },
  reportButtonText: { color: "#0f172a", fontWeight: "600", fontSize: 14 },
  empty: { textAlign: "center", color: "#94a3b8", marginTop: 40 },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  modalContent: { backgroundColor: "#fff", borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 },
  modalTitle: { fontSize: 18, fontWeight: "700", marginBottom: 12 },
  input: { borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 8, padding: 12, marginBottom: 10 },
  cancelButton: { alignItems: "center", padding: 10, marginTop: 4 },
  cancelButtonText: { color: "#64748b" },
});
