import React, { useEffect } from "react";
import { StatusBar, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppNavigator } from "./src/navigation/AppNavigator";
import { colors } from "./src/utils/theme";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 10000 },
  },
});

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <StatusBar barStyle="light-content" backgroundColor={colors.background} />
        <View style={{ flex: 1, backgroundColor: colors.background }}>
          <AppNavigator />
        </View>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
