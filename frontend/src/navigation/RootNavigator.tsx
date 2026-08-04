// RootNavigator.tsx
// Conditional rendering between Landing -> Auth -> Dashboard with tab navigator.
// Phase: DESIGN

import React, { useEffect, useState } from 'react';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, ActivityIndicator, useColorScheme } from 'react-native';

import { LandingScreen } from '../screens/LandingScreen';
import { HomeScreen } from '../screens/HomeScreen';
import { CanvasScreen } from '../screens/CanvasScreen';
import { StoryboardScreen } from '../screens/StoryboardScreen';
import { MyAssetsScreen } from '../screens/MyAssetsScreen';
import { StyleLibraryScreen } from '../screens/StyleLibraryScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { TabNavigator } from './TabNavigator';
import { useAuthStore } from '../state/authStore';

const Stack = createNativeStackNavigator();

const OioiDarkTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: '#0A0A0B',
    card: '#111114',
    primary: '#7C3AED',
    text: '#F5F5F7',
    border: '#FFFFFF14',
  },
};

const OioiLightTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: '#FAFAFB',
    primary: '#7C3AED',
  },
};

export type RootStackParamList = {
  Landing: undefined;
  Main: undefined;
  StyleLibrary: undefined;
  Settings: undefined;
};

export const RootNavigator: React.FC = () => {
  const scheme = useColorScheme();
  const theme = scheme === 'light' ? OioiLightTheme : OioiDarkTheme;
  const { token, hydrated, hydrate } = useAuthStore();
  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        await hydrate();
      } catch (e) {
        setBootError((e as Error).message);
      }
    })();
  }, [hydrate]);

  if (!hydrated) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0A0A0B' }}>
        <ActivityIndicator color="#7C3AED" size="large" />
     </View>
    );
  }

  if (bootError) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0A0A0B', padding: 24 }}>
        <ActivityIndicator color="#EF4444" />
     </View>
    );
  }

  return (
    <NavigationContainer theme={theme}>
      <Stack.Navigator
        screenOptions={{
          headerShown: false,
          animation: 'slide_from_right',
          contentStyle: { backgroundColor: '#0A0A0B' },
        }}
        initialRouteName={token ? 'Main' : 'Landing'}
      >
        <Stack.Screen name="Landing" component={LandingScreen} />
        <Stack.Screen name="Main" component={TabNavigator} />
        <Stack.Screen name="StyleLibrary" component={StyleLibraryScreen} options={{ headerShown: true, title: 'Style Library' }} />
        <Stack.Screen name="Settings" component={SettingsScreen} options={{ headerShown: true, title: 'Settings' }} />
     </Stack.Navigator>
   </NavigationContainer>
  );
};

export default RootNavigator;
