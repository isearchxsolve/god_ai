// TabNavigator.tsx
// 5-tab bottom navigator for Home, Canvas, Storyboard, MyAssets, Settings.
// Phase: DESIGN

import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { View, Text, StyleSheet, Platform } from 'react-native';

import { HomeScreen } from '../screens/HomeScreen';
import { CanvasScreen } from '../screens/CanvasScreen';
import { StoryboardScreen } from '../screens/StoryboardScreen';
import { MyAssetsScreen } from '../screens/MyAssetsScreen';
import { SettingsScreen } from '../screens/SettingsScreen';

export type TabParamList = {
  Home: undefined;
  Canvas: undefined;
  Storyboard: undefined;
  MyAssets: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<TabParamList>();

type IconProps = { focused: boolean; label: string; glyph: string };

const TabIcon: React.FC<IconProps> = ({ focused, label, glyph }) => (
  <View style={styles.iconWrap} accessibilityLabel={label}>
    <Text style={[styles.glyph, focused && styles.glyphFocused]}>{glyph</Text>
    <Text style={[styles.label, focused && styles.labelFocused]}>{label</Text>
 </View>
);

export const TabNavigator: React.FC = () => {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: styles.tabBar,
        tabBarItemStyle: styles.tabItem,
        tabBarHideOnKeyboard: true,
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} label="Home" glyph="\u2302" />
          ),
        }}
      />
      <Tab.Screen
        name="Canvas"
        component={CanvasScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} label="Canvas" glyph="\u25A2" />
          ),
        }}
      />
      <Tab.Screen
        name="Storyboard"
        component={StoryboardScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} label="Storyboard" glyph="\u25B6" />
          ),
        }}
      />
      <Tab.Screen
        name="MyAssets"
        component={MyAssetsScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} label="Assets" glyph="\u2B22" />
          ),
        }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} label="Settings" glyph="\u2699" />
          ),
        }}
      />
   </Tab.Navigator>
  );
};

const styles = StyleSheet.create({
  tabBar: {
    position: 'absolute',
    bottom: Platform.select({ ios: 24, android: 16, default: 16 }),
    left: 16,
    right: 16,
    height: 68,
    backgroundColor: '#111114',
    borderTopWidth: 0,
    borderRadius: 22,
    paddingHorizontal: 8,
    paddingBottom: 8,
    paddingTop: 8,
    borderWidth: 1,
    borderColor: '#FFFFFF14',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.35,
    shadowRadius: 24,
    elevation: 12,
  },
  tabItem: {
    borderRadius: 16,
  },
  iconWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 6,
  },
  glyph: {
    fontSize: 20,
    color: '#9CA3AF',
    marginBottom: 2,
  },
  glyphFocused: {
    color: '#7C3AED',
  },
  label: {
    fontSize: 10,
    color: '#9CA3AF',
    fontWeight: '500',
    letterSpacing: 0.3,
  },
  labelFocused: {
    color: '#F5F5F7',
    fontWeight: '700',
  },
});

export default TabNavigator;
