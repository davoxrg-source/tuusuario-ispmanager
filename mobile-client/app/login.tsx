import { useState } from "react";
import { ActivityIndicator, Alert, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useAuth } from "../src/auth/AuthContext";

export default function Login() {
  const { signIn } = useAuth();
  const [identification, setIdentification] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!identification || !password) return;
    setLoading(true);
    try {
      await signIn(identification, password);
    } catch {
      Alert.alert("No se pudo iniciar sesión", "Verificá tu identificación y contraseña.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>ISP Manager</Text>
      <Text style={styles.subtitle}>Portal de clientes</Text>

      <TextInput
        style={styles.input}
        placeholder="Identificación (cédula/NIT)"
        value={identification}
        onChangeText={setIdentification}
        autoCapitalize="none"
        keyboardType="number-pad"
      />
      <TextInput
        style={styles.input}
        placeholder="Contraseña"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <TouchableOpacity style={styles.button} onPress={handleSubmit} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Ingresar</Text>}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#fff" },
  title: { fontSize: 24, fontWeight: "700", textAlign: "center", color: "#0f172a" },
  subtitle: { fontSize: 14, textAlign: "center", color: "#64748b", marginBottom: 32 },
  input: {
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 16,
  },
  button: { backgroundColor: "#0f172a", borderRadius: 8, padding: 14, alignItems: "center", marginTop: 8 },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
