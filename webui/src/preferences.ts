import { defineOverridesPreferences } from '@vben/preferences';

/**
 * AI4SE 操作台：保留 Vben 左侧导航
 */
export const overridesPreferences = defineOverridesPreferences({
  app: {
    name: import.meta.env.VITE_APP_TITLE,
    accessMode: 'frontend',
    defaultHomePath: '/workbench',
    enableCheckUpdates: false,
    enableCopyPreferences: false,
    enablePreferences: false,
    layout: 'sidebar-nav',
  },
  breadcrumb: {
    enable: false,
  },
  copyright: {
    enable: false,
  },
  footer: {
    enable: false,
  },
  header: {
    enable: true,
    height: 48,
    mode: 'fixed',
  },
  logo: {
    enable: true,
    source: '',
  },
  shortcutKeys: {
    enable: false,
  },
  sidebar: {
    collapsed: false,
    width: 200,
  },
  tabbar: {
    enable: false,
  },
  theme: {
    mode: 'auto',
  },
  widget: {
    fullscreen: false,
    globalSearch: false,
    languageToggle: false,
    lockScreen: false,
    notification: false,
    refresh: false,
    sidebarToggle: true,
    themeToggle: true,
    timezone: false,
  },
});
