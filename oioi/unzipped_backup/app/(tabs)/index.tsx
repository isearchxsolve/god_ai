import { Text, View, StyleSheet } from 'react-native'
export default function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>oioi</Text>
      <Text style={styles.sub}>Build a true, production-grade clone of oiioii.ai You are taking over the existing `oioi` codebase (React + Vite frontend + FastAPI backend + 7-agent pipeline + free-tier providers). The expo-node scaffold will be generated on autopilot start — augment it, fix errors, add real NIM-powered features, and verify the full stack works.</Text>
    </View>
  )
}
const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0f172a' },
  title: { fontSize: 32, fontWeight: '700', color: '#38bdf8', marginBottom: 8 },
  sub: { fontSize: 16, color: '#94a3b8' },
})
